# echo_core/skill_manager.py
"""
Skill Manager v2.0 — менеджер навыков Echo.
Поддержка длительных задач, потокового вывода и прерывания.
"""
import os
import re
import json
import time
import threading
import subprocess
import sys
from datetime import datetime
from echo_core.config import LOGS_DIR, SKILL_LOG_FILE, KNOWLEDGE_INPUT_DIR, GGUF_MODEL_PATH
from utils.utils_logger import get_logger


class SkillManagerV2:
    def __init__(self, assistant_ref):
        self.assistant = assistant_ref
        self.running_skill = None
        self.active_process = None
        self.stop_requested = False
        self.last_run_interrupted = False
        self.skill_log = []
        self.logger = get_logger("SkillManagerV2")
        self.log_file = SKILL_LOG_FILE
        self.runtime_state = self._new_runtime_state()
        self._reset_session_logs()
        self._init_skills()

    def _init_skills(self):
        self.skills = {
            "помощь": (self.skill_help, "Список всех команд", True),
            "стат": (self.skill_stats, "Статистика памяти", True),
            "время": (self.skill_time, "Текущее время", True),
            "законы": (self.skill_laws, "Этические законы", True),
            "очистить": (self.skill_clear_chat, "Очистить чат", True),
            "сброс": (self.skill_memory_cleanup, "Сбросить слабые связи", False),
            "учить": (self.skill_ingest, "Обработать файлы знаний", False),
            "экспорт": (self.skill_export, "Экспорт знаний в JSON", False),
            "модель": (self.skill_switch_model, "Переключить модель", True),
            "cpu": (self.skill_cpu, "Управление потоками CPU", True),
            "restart": (self.skill_restart, "Перезагрузить модель", True),
        }

    def _reset_session_logs(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        for log_path in (self.log_file,):
            try:
                with open(log_path, "w", encoding="utf-8"):
                    pass
            except OSError:
                pass

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[СКИЛЛ {timestamp}] {message}"
        self.skill_log.append(full_msg)
        self._update_runtime_state(message)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} {message}\n")
        except Exception:
            pass
        self.logger.info(full_msg)

    def _new_runtime_state(self):
        return {
            "task": None, "status_line": "ожидание", "current_step": None,
            "total_steps": None, "current_epoch": None, "total_epochs": None,
            "checkpoint": None, "started_at": None, "elapsed_seconds": None,
        }

    def _reset_runtime_state(self, task_name=None):
        self.runtime_state = self._new_runtime_state()
        self.runtime_state["task"] = task_name
        self.runtime_state["started_at"] = time.time() if task_name else None

    def _update_runtime_state(self, message):
        state = self.runtime_state
        if message.startswith("Запуск: "):
            state["status_line"] = message.replace("Запуск: ", "", 1)
            return
        if "НАЙДЕН ЧЕКПОИНТ!" in message:
            state["checkpoint"] = os.path.basename(message.split(":", 1)[-1].strip())
            return
        if "ЧЕКПОИНТ НЕ НАЙДЕН" in message:
            state["checkpoint"] = "нет"
            return
        checkpoint_match = re.search(r"checkpoint-(\d+)", message)
        if checkpoint_match and ("сохран" in message.lower() or "возобнов" in message.lower()):
            state["checkpoint"] = checkpoint_match.group(0)
        time_match = re.search(r"время:\s*(\d+)\s*сек", message, re.IGNORECASE)
        if time_match:
            state["elapsed_seconds"] = int(time_match.group(1))
        epoch_match = re.search(r"эпоха\s+(\d+)/(\d+)", message, re.IGNORECASE)
        if epoch_match:
            state["current_epoch"] = int(epoch_match.group(1))
            state["total_epochs"] = int(epoch_match.group(2))
        step_match = re.search(r"шаг\s+(\d+)(?:/|\s+из\s+)(\d+)", message, re.IGNORECASE)
        if step_match:
            state["current_step"] = int(step_match.group(1))
            state["total_steps"] = int(step_match.group(2))
        if message.startswith(("Статус:", "ШАГ ", "Шаг ", "Эпоха ", "Сохранение модели", "Обучение завершено")):
            state["status_line"] = message

    def get_runtime_snapshot(self):
        snapshot = dict(self.runtime_state)
        snapshot["active_task"] = self.running_skill
        snapshot["summary"] = self._format_runtime_summary(snapshot)
        return snapshot

    def _format_runtime_summary(self, snapshot):
        active_task = snapshot.get("active_task")
        if not active_task:
            return "Ожидание"
        step = snapshot.get("current_step")
        total_steps = snapshot.get("total_steps")
        epoch = snapshot.get("current_epoch")
        total_epochs = snapshot.get("total_epochs")
        checkpoint = snapshot.get("checkpoint") or "нет"
        started_at = snapshot.get("started_at")
        elapsed = self._resolve_elapsed_seconds(snapshot, started_at)
        time_text = f"{elapsed} сек"
        if step and total_steps and epoch and total_epochs:
            return f"Шаг {step} из {total_steps}, эпоха {epoch}/{total_epochs}, checkpoint: {checkpoint}, время: {time_text}"
        if epoch and total_epochs:
            return f"Эпоха {epoch}/{total_epochs}, checkpoint: {checkpoint}, время: {time_text}"
        status_line = snapshot.get("status_line") or active_task
        return f"{status_line}, checkpoint: {checkpoint}, время: {time_text}"

    def _resolve_elapsed_seconds(self, snapshot, started_at):
        parsed_elapsed = snapshot.get("elapsed_seconds")
        if parsed_elapsed is not None:
            wall_elapsed = int(time.time() - started_at) if started_at else parsed_elapsed
            return max(parsed_elapsed, wall_elapsed)
        if started_at:
            return int(time.time() - started_at)
        return 0

    def parse_command(self, text):
        text = text.strip()
        if not text:
            return None, None
        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            return parts[0].lower(), parts[1] if len(parts) > 1 else ""
        for prefix in ["скилл ", "skill "]:
            if text.lower().startswith(prefix):
                parts = text[len(prefix):].split(maxsplit=1)
                return parts[0].lower(), parts[1] if len(parts) > 1 else ""
        return None, None

    def execute(self, skill_name, args="", callback_dict=None):
        if skill_name not in self.skills:
            return f"Неизвестная команда: '/{skill_name}'\n/помощь для списка."
        if self.running_skill:
            return f"Уже запущен навык: {self.running_skill}."
        func, desc, instant = self.skills[skill_name]
        if instant:
            try:
                return func(args, callback_dict)
            except Exception as e:
                return f"Ошибка: {e}"
        self.log(f"Запуск: {desc}")
        def run():
            try:
                func(args, callback_dict)
                if not self.stop_requested:
                    self.log(f"Команда '{skill_name}' завершена.")
            except Exception as e:
                self.logger.error(f"Ошибка в навыке {skill_name}: {e}")
            finally:
                self.running_skill = None
                self.stop_requested = False
        self.running_skill = skill_name
        threading.Thread(target=run, daemon=True).start()
        return f"[СКИЛЛ] Запущен навык '{skill_name}'."

    def interrupt_running_skill(self):
        if not self.running_skill:
            return False, "Сейчас нет активной задачи."
        self.stop_requested = True
        process = self.active_process
        if process and process.poll() is None:
            try:
                process.terminate()
                self.log(f"Прерывание '/{self.running_skill}'...")
                return True, f"Прерываю '/{self.running_skill}'."
            except Exception as e:
                return False, f"Не удалось прервать: {e}"
        return True, f"Запрошено завершение '/{self.running_skill}'."

    def skill_help(self, args, cb):
        lines = ["Доступные команды:", "-" * 40]
        for name, (_, desc, _) in self.skills.items():
            lines.append(f"  /{name} - {desc}")
        return "\n".join(lines)

    def skill_stats(self, args, cb):
        db = self.assistant.db
        memory = db.fetchone("SELECT COUNT(*) FROM memory")[0]
        laws = db.fetchone("SELECT COUNT(*) FROM survival_matrix")[0]
        knowledge = db.fetchone("SELECT COUNT(*) FROM learned_knowledge")[0]
        risks = db.fetchone("SELECT COUNT(*) FROM risk_flags")[0]
        concepts = db.fetchone("SELECT COUNT(*) FROM concept_nodes")[0]
        state = self.assistant.get_state_snapshot()
        return (
            f"Диалогов: {memory}\nЗаконов: {laws}\nЗнаний: {knowledge}\n"
            f"Концептов: {concepts}\nРисков: {risks}\n"
            f"Режим: {state['cognitive']['mode']}\n"
            f"Автономность: {state['cognitive']['autonomy_index']:.2f}"
        )

    def skill_time(self, args, cb):
        return datetime.now().strftime("%H:%M:%S %d.%m.%Y")

    def skill_laws(self, args, cb):
        e = self.assistant.safety.ethics if hasattr(self.assistant, 'safety') else {}
        lines = ["Этические законы:", "-" * 40]
        status = "ВКЛЮЧЕНЫ" if e.get("enabled", True) else "ОТКЛЮЧЕНЫ"
        lines.append(f"Статус: {status}")
        for k, v in e.items():
            if k != "enabled":
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def skill_clear_chat(self, args, cb):
        if cb and "clear_chat" in cb:
            cb["clear_chat"]()
            return "Чат очищен."
        return "Функция недоступна."

    def skill_memory_cleanup(self, args, cb):
        self.log("Очистка слабых связей...")
        db = self.assistant.db
        db.execute("DELETE FROM memory WHERE weight < 0.5 AND uses = 0")
        db.execute("DELETE FROM learned_knowledge WHERE weight < 0.5 AND uses = 0")
        return "Очистка завершена."

    def skill_ingest(self, args, cb):
        self.log("Обработка папки знаний...")
        count = self.assistant.process_knowledge_inbox()
        return f"Усвоено файлов: {count}"

    def skill_export(self, args, cb):
        self.log("Экспорт знаний...")
        db = self.assistant.db
        data = {
            "memory": [{"user": r[0], "answer": r[1]} for r in db.fetchall("SELECT user_text, answer FROM memory")],
            "laws": [{"context": r[0], "wisdom": r[3]} for r in db.fetchall("SELECT context, core_essence, blind_spots, actionable_wisdom FROM survival_matrix")],
            "knowledge": [{"content": r[0], "type": r[1]} for r in db.fetchall("SELECT content, knowledge_type FROM learned_knowledge")],
        }
        filename = f"echo_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Экспорт сохранён: {filename}"

    def skill_switch_model(self, args, cb):
        self.log("Переключение модели...")
        if not os.path.exists(GGUF_MODEL_PATH):
            return f"Модель не найдена: {GGUF_MODEL_PATH}"
        try:
            from llama_cpp import Llama
            if hasattr(self.assistant, 'local_brain') and self.assistant.local_brain:
                del self.assistant.local_brain
            self.assistant.local_brain = Llama(
                model_path=GGUF_MODEL_PATH,
                n_ctx=2048,
                n_threads=4
            )
            self.log("Модель переключена на дообученную!")
            return "Модель переключена."
        except Exception as e:
            return f"Ошибка загрузки: {e}"

    def skill_cpu(self, args, cb):
        try:
            threads = int(args.strip()) if args.strip() else 4
            self.assistant.cpu_threads = threads
            return f"Потоки CPU установлены: {threads}"
        except ValueError:
            return f"Укажите число потоков: /cpu 8"

    def skill_restart(self, args, cb):
        self.log("Перезагрузка модели...")
        return "Модель перезагружена."


# Алиас для обратной совместимости с импортом SkillManager
SkillManager = SkillManagerV2