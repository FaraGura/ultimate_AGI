# echo_core/crystallization.py
"""
Автономная Фаза Сна (Crystallization Engine).
Использует LM Studio для извлечения законов и концептов.
Пишет причинные связи напрямую в Causal Graph.
Поддерживает «Ленивую эволюцию» — уточнение законов при ошибках.
Генерирует core_axioms.md после обработки.
"""
import os
import re
import json
import gc
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from echo_core.config import KNOWLEDGE_INPUT_DIR
from utils.utils_logger import get_logger


class CrystallizationEngine:
    SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".tsv"}
    READ_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251")

    FAILURE_TRIGGERS = [
        "ошибка", "провал", "не сработало", "не удалось", "факап",
        "минус", "проиграл", "потерял", "сломал", "разрушил",
        "не получилось", "fail", "error", "wrong"
    ]

    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

    def __init__(self, db, causal_graph, system1=None, homeostasis_monitor=None):
        self.db = db
        self.causal = causal_graph
        self.system1 = system1
        self.homeostasis = homeostasis_monitor
        self.logger = get_logger("Crystallization")

    # Безопасная прослойка для работы с кастомной DB или sqlite3
    def _db_execute(self, query: str, params: tuple = ()):
        try:
            if hasattr(self.db, "execute"):
                self.db.execute(query, params)
            elif hasattr(self.db, "cursor"):
                cur = self.db.cursor()
                cur.execute(query, params)
                self.db.commit()
        except Exception as e:
            self.logger.error(f"Ошибка SQL: {e}")

    def _db_fetchall(self, query: str, params: tuple = ()):
        try:
            if hasattr(self.db, "fetchall"):
                return self.db.fetchall(query, params)
            elif hasattr(self.db, "cursor"):
                cur = self.db.cursor()
                cur.execute(query, params)
                return cur.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка SQL: {e}")
            return []

    # ─── Чтение файлов ────────────────────────────────────────────
    def _read_text_with_fallback(self, path: Path) -> Optional[str]:
        for enc in self.READ_ENCODINGS:
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, OSError):
                continue
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def read_knowledge_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        text = self._read_text_with_fallback(path)
        if not text:
            return ""
        try:
            if suffix in {".txt", ".md", ".markdown", ".csv", ".tsv"}:
                return text
            if suffix == ".json":
                return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            if suffix == ".jsonl":
                lines = []
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        lines.append(json.dumps(json.loads(line), ensure_ascii=False))
                    except json.JSONDecodeError:
                        lines.append(line)
                return "\n".join(lines)
        except Exception:
            return text
        return text

    def split_large_text(self, text, chunk_chars=1200, overlap=180, min_chunk_chars=220):
        text = re.sub(r"\r\n?", "\n", str(text or "")).strip()
        if not text:
            return []
        chunks = []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        buffer = ""
        for paragraph in paragraphs:
            if len(paragraph) > chunk_chars:
                if buffer:
                    chunks.append(buffer.strip())
                    buffer = ""
                step = max(1, chunk_chars - overlap)
                for start in range(0, len(paragraph), step):
                    piece = paragraph[start:start + chunk_chars].strip()
                    if len(piece) >= min_chunk_chars:
                        chunks.append(piece)
                continue
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= chunk_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer.strip())
                buffer = paragraph
        if buffer:
            chunks.append(buffer.strip())
        return [c for c in chunks if len(c) >= min_chunk_chars]

    def ingest_knowledge_file(self, filename: str, max_size_mb=10) -> List[str]:
        if not os.path.exists(KNOWLEDGE_INPUT_DIR):
            os.makedirs(KNOWLEDGE_INPUT_DIR, exist_ok=True)
            return []
        file_path = Path(KNOWLEDGE_INPUT_DIR) / filename
        if not file_path.exists():
            return []
        if file_path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            self.logger.warning(f"Неподдерживаемый формат: {file_path.suffix}")
            return []
        if os.path.getsize(file_path) / (1024 * 1024) > max_size_mb:
            return self._chunked_ingest(str(file_path))
        self.logger.info(f"Источник: {filename}. Считывание...")
        raw_text = self.read_knowledge_file(file_path)
        if not raw_text.strip():
            return []
        chunks = self.split_large_text(raw_text)
        if chunks:
            self.logger.info(f"Считано блоков: {len(chunks)}")
            return chunks
        return self.split_large_text(raw_text, min_chunk_chars=40)

    def _chunked_ingest(self, file_path: str, chunk_size=1000) -> List[str]:
        paragraphs = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chunk = []
                for line in f:
                    chunk.append(line)
                    if len(chunk) >= chunk_size:
                        paragraphs.append("".join(chunk))
                        chunk = []
                if chunk:
                    paragraphs.append("".join(chunk))
        except Exception as e:
            self.logger.error(f"Ошибка чтения: {e}")
        return paragraphs

    # ─── Сохранение в память ──────────────────────────────────────
    def _save_to_memory(self, text: str):
        try:
            self._db_execute(
                "INSERT INTO memory (user_text, answer, weight, uses, created) VALUES (?, ?, ?, 0, ?)",
                (text, "", 0.5, str(datetime.now()))
            )
            self.logger.info("Чанк сохранён в диалоговую память.")
        except Exception as e:
            self.logger.error(f"Не удалось сохранить чанк: {e}")

    # ─── HTTP-клиент к LM Studio ──────────────────────────────────
    def _call_lm_studio(self, system_prompt: str, user_prompt: str, max_tokens=1200) -> Optional[Dict[str, Any]]:
        payload = {
            "model": "auto",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "top_p": 0.1,
            "max_tokens": max_tokens,
            "stop": ["```", "<end_of_turn>"]
        }
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.LM_STUDIO_URL, data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode('utf-8')
                result = json.loads(body)
                msg = result["choices"][0]["message"]
                raw_content = msg.get("reasoning_content") or msg.get("content", "")

            # Очистка BOM + непечатных символов
            raw_content = raw_content.encode('utf-8').decode('utf-8-sig').strip()

            # Извлекаем JSON-объект — даже если вокруг есть мусор
            match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if not match:
                self.logger.warning("JSON-объект не найден в ответе")
                self._save_to_memory(user_prompt[:500])
                return None

            json_str = match.group(0)
            self.logger.info(f"JSON до парсинга: {json_str[:200]}")
            try:
                result = json.loads(json_str, strict=False)
                self.logger.info("JSON успешно распарсен")
                return result
            except json.JSONDecodeError as e:
                self.logger.warning(f"Ошибка парсинга JSON: {e}")

            # Восстанавливаем закрывающие скобки, если не хватает
            open_braces = json_str.count('{') - json_str.count('}')
            open_brackets = json_str.count('[') - json_str.count(']')
            if open_braces > 0:
                json_str += '}' * open_braces
            if open_brackets > 0:
                json_str += ']' * open_brackets

            # Пытаемся распарсить с ослабленным режимом
            try:
                return json.loads(json_str, strict=False)
            except json.JSONDecodeError as e:
                self.logger.warning(f"Невалидный JSON после восстановления: {e}")
                self._save_to_memory(user_prompt[:500])
                return None

        except Exception as e:
            self.logger.error(f"Ошибка LM Studio: {e}")
            return None

    # ─── Извлечение законов через LM Studio ────────────────────────
    def _extract_law_with_qwen(self, paragraph: str) -> Optional[Dict[str, Any]]:
        system = (
            "Ты — JSON-конвейер. Отвечай ТОЛЬКО валидным JSON без вступлений и рассуждений.\n"
            "Пример: {\"core_essence\":\"Мастерство требует практики\", "
            "\"actionable_wisdom\":\"Тренируйтесь ежедневно\", "
            "\"concepts\":[\"мастерство\",\"практика\",\"развитие\"]}"
        )
        user = f"Текст:\n{paragraph[:1500]}\n\nЗАДАНИЕ: Выдели законы. Ответ: {{"
        return self._call_lm_studio(system, user, max_tokens=1200)

    def _evolve_law_with_qwen(self, paragraph: str, old_law: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        system = (
            "Ты — JSON-конвейер. Отвечай ТОЛЬКО валидным JSON без вступлений и рассуждений.\n"
            "Пример: {\"updated_core_essence\":\"Уточнённый закон\", "
            "\"confidence_penalty\":0.15, \"new_exception\":\"Описание исключения\"}"
        )
        user = (
            f"СТАРЫЙ ЗАКОН: {old_law.get('core_essence', '')}\n"
            f"СУТЬ ПРОТИВОРЕЧИЯ: {paragraph[:1000]}\n\n"
            f"ЗАДАНИЕ: Уточни закон. Ответ: {{"
        )
        return self._call_lm_studio(system, user, max_tokens=1200)

    # ─── Поиск старого закона ─────────────────────────────────────
    def _find_contradicted_law(self, paragraph: str) -> Optional[Dict[str, Any]]:
        rows = self._db_fetchall(
            "SELECT id, context, core_essence, actionable_wisdom, confidence_score, failure_exceptions "
            "FROM survival_matrix ORDER BY id DESC"
        )
        if not rows:
            return None
        para_lower = paragraph.lower()
        for row in rows:
            law_id, context, essence, wisdom, conf, exceptions = row
            if len(set(context.lower().split()) & set(para_lower.split())) >= 3:
                return {
                    "id": law_id, "context": context, "core_essence": essence,
                    "actionable_wisdom": wisdom, "confidence_score": conf,
                    "failure_exceptions": exceptions,
                }
        return None

    # ─── Нормализация ключей ──────────────────────────────────────
    def _normalize_law(self, law: Dict[str, Any]) -> Dict[str, Any]:
        if "laws" in law and isinstance(law["laws"], list) and len(law["laws"]) > 0:
            law["core_essence"] = law["laws"][0]
            if "actionable_wisdom" not in law:
                law["actionable_wisdom"] = law["laws"][0]
            if "concepts" not in law:
                law["concepts"] = law["laws"][1:] if len(law["laws"]) > 1 else []
        if not law.get("core_essence"):
            for key in ["core_essence", "updated_core_essence", "essence", "law", "rule"]:
                if key in law and law[key]:
                    law["core_essence"] = law[key]
                    break
        if not law.get("actionable_wisdom") and law.get("core_essence"):
            law["actionable_wisdom"] = law["core_essence"]
        self.logger.info(f"После нормализации: core='{law.get('core_essence','')}', wisdom='{law.get('actionable_wisdom','')}'")
        return law

    # ─── Главный цикл обработки файла ─────────────────────────────
    def crystallize_file(self, filename: str) -> int:
        paragraphs = self.ingest_knowledge_file(filename)
        if not paragraphs:
            self.logger.info(f"Файл '{filename}' пуст.")
            return 0

        laws_learned = 0
        for paragraph in paragraphs:
            if self.homeostasis and self.homeostasis.get_state().get("throttling"):
                self.logger.warning("Троттлинг GPU – остановка.")
                break

            has_failure = any(t in paragraph.lower() for t in self.FAILURE_TRIGGERS)

            if has_failure:
                old = self._find_contradicted_law(paragraph)
                if old:
                    self.logger.info(f"Маркер ошибки, уточняю закон #{old['id']}")
                    evolved = self._evolve_law_with_qwen(paragraph, old)
                    if evolved:
                        evolved = self._normalize_law(evolved)
                        penalty = evolved.get("confidence_penalty", 0.1)
                        new_score = max(0.0, round(old["confidence_score"] - penalty, 2))
                        new_essence = evolved.get("updated_core_essence", old["core_essence"]).strip()
                        try:
                            exc = json.loads(old["failure_exceptions"])
                        except Exception:
                            exc = []
                        exc.append(evolved.get("new_exception", paragraph[:100]))
                        if new_score <= 0.1:
                            self._db_execute("DELETE FROM survival_matrix WHERE id = ?", (old["id"],))
                            self.logger.info(f"Закон #{old['id']} удалён.")
                        else:
                            self._db_execute(
                                "UPDATE survival_matrix SET confidence_score=?, core_essence=?, "
                                "actionable_wisdom=?, failure_exceptions=? WHERE id=?",
                                (new_score, new_essence,
                                 evolved.get("updated_actionable_wisdom", old["actionable_wisdom"]).strip(),
                                 json.dumps(exc, ensure_ascii=False), old["id"]))
                            self.logger.info(f"Закон #{old['id']} уточнён (score={new_score}).")
                        laws_learned += 1
                        continue

            # Обычное извлечение
            law = self._extract_law_with_qwen(paragraph)
            if not law:
                continue
            law = self._normalize_law(law)
            essence = law.get("core_essence", "").strip()
            wisdom = law.get("actionable_wisdom", "").strip()
            if not essence or not wisdom:
                continue

            context = law.get("context", paragraph[:120]).strip()
            blind = law.get("blind_spots", "").strip()
            concepts = law.get("concepts", [])
            if isinstance(concepts, str):
                concepts = [c.strip() for c in concepts.split(",") if c.strip()]
            relations = law.get("relations", [])
            tags = json.dumps(law.get("tags", []), ensure_ascii=False)

            self._db_execute(
                '''INSERT OR REPLACE INTO survival_matrix
                   (context, core_essence, blind_spots, actionable_wisdom, confidence_score,
                    failure_exceptions, tags, reflex_level, created)
                   VALUES (?,?,?,?,1.0,'[]',?,0,?)''',
                (context, essence, blind, wisdom, tags, str(datetime.now()))
            )
            laws_learned += 1   # <--- ВОТ ЭТА СТРОКА БЫЛА ПОТЕРЯНА

            for c in concepts:
                if c:
                    self._db_execute(
                        "INSERT OR IGNORE INTO concept_nodes (concept, surface_truth, confidence, last_used) "
                        "VALUES (?,?,0.8,?)",
                        (c, wisdom[:200], str(datetime.now()))
                    )
            for rel in relations:
                src = rel.get("source", "").strip()
                tgt = rel.get("target", "").strip()
                rtype = rel.get("type", "correlation")
                if src and tgt:
                    if not (rtype == "contradiction" and self.causal.validate_path(src, tgt)):
                        self.causal.add_edge(src, tgt, rtype, confidence=0.7)
                        laws_learned += 1
            gc.collect()

        self._generate_core_axioms()
        return laws_learned

    # ─── Генерация core_axioms.md ─────────────────────────────────
    def _generate_core_axioms(self):
        try:
            rows = self._db_fetchall(
                "SELECT context, core_essence, blind_spots, actionable_wisdom, confidence_score, failure_exceptions "
                "FROM survival_matrix ORDER BY confidence_score DESC"
            )
            if not rows:
                return
            with open("core_axioms.md", "w", encoding="utf-8") as md:
                md.write("# ⚡ МАТРИЦА УНИВЕРСАЛЬНЫХ ПРИОРИТЕТОВ ЭХО (ЯДРО ЯН)\n")
                md.write(f"*Кристаллизация: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
                for row in rows:
                    ctx, ess, blind, wis, score, exc = row
                    md.write(f"## 🌐 Контекст: {ctx} [Confidence: {score}]\n")
                    md.write(f"- **🎯 Суть:** {ess}\n- **🚨 Слепые зоны:** {blind}\n- **💀 Мудрость:** {wis}\n")
                    try:
                        ex_list = json.loads(exc)
                        if ex_list:
                            md.write("- **⚠️ Исключения:**\n")
                            for ex in ex_list:
                                md.write(f"  * {ex}\n")
                    except Exception:
                        pass
                    md.write("\n---\n\n")
            self.logger.info("Манифест обновлён.")
        except Exception as e:
            self.logger.error(f"Ошибка core_axioms.md: {e}")

    # ─── Обработка всей папки ─────────────────────────────────────
    def process_inbox(self) -> int:
        if not os.path.exists(KNOWLEDGE_INPUT_DIR):
            os.makedirs(KNOWLEDGE_INPUT_DIR, exist_ok=True)
            return 0
        files = [f for f in os.listdir(KNOWLEDGE_INPUT_DIR)
                 if os.path.isfile(os.path.join(KNOWLEDGE_INPUT_DIR, f)) and f.endswith(".txt")]
        if not files:
            self.logger.info("Папка знаний пуста.")
            return 0
        total = 0
        for f in files:
            self.logger.info(f"Начинаю кристаллизацию: {f}")
            learned = self.crystallize_file(f)
            if learned >= 0:
                os.remove(os.path.join(KNOWLEDGE_INPUT_DIR, f))
                total += learned
                self.logger.info(f"Файл '{f}' усвоен. Новых/уточнённых законов: {learned}")
        return total