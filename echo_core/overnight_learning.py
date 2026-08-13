# echo_core/overnight_learning.py
import json
import time, threading, re
from datetime import datetime, timedelta
from typing import Optional, Callable

try:
    import requests
except ImportError:  # pragma: no cover - depends on environment
    requests = None

from echo_core.causal_graph import normalize

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
PRONOUN_SUBJECTS = {"тебя", "это", "он", "она", "они", "меня", "нас", "вас"}
ADVERB_SUBJECTS = {"часто", "иногда", "очень", "совсем", "просто", "всегда", "редко"}
MAX_EMPTY_RESPONSES_IN_ROW = 10


class _FallbackResponse:
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return json.loads(self._body or "{}")

    def text(self) -> str:
        return self._body


def _post_json(url: str, payload: dict, timeout: int = 180):
    if requests is not None:
        return requests.post(url, json=payload, timeout=timeout)

    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return _FallbackResponse(resp.getcode(), body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return _FallbackResponse(exc.code, body)

STOP_QUERY_WORDS = {
    "нет", "да", "это", "то", "что", "как", "почему", "где", "когда",
    "кто", "какой", "какая", "такое", "такой", "такая", "такие",
    "или", "и", "не", "но", "бы", "ли", "же", "вот", "уже", "ещё",
    "там", "тут", "здесь", "теперь", "тогда", "также", "тоже",
    "всё", "все", "весь", "весьма", "очень", "совсем", "просто",
    "вообще", "например", "конечно", "наверное", "наверно",
    "возможно", "вероятно", "обычно", "часто", "иногда", "редко",
    "всегда", "никогда", "опять", "снова", "вдруг", "вроде",
    "типа", "как-то", "что-то", "где-то", "кто-то", "почему-то",
    "пофиг", "ладно", "ок", "ага", "угу", "мм", "хм",
    "prep_about_obj", "prep_off", "act_stand", "adj_fast",
}

ADJ_ENDINGS = {"ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие"}
FALSE_ADJECTIVES = {"понятие", "здание", "собрание", "решение", "мнение", "среднее", "существо", "животное", "насекомое", "растение"}


def _ensure_asked_table(core):
    core.db.execute("CREATE TABLE IF NOT EXISTS asked_concepts (concept TEXT PRIMARY KEY, asked_at TEXT)")

def _is_already_asked(core, concept: str) -> bool:
    row = core.db.fetchone("SELECT 1 FROM asked_concepts WHERE concept = ?", (concept.lower(),))
    return row is not None

def _mark_as_asked(core, concept: str):
    core.db.execute("INSERT OR IGNORE INTO asked_concepts (concept, asked_at) VALUES (?, ?)", (concept.lower(), datetime.now().isoformat()))

def _purge_llm_facts(core):
    try:
        core.db.execute("DELETE FROM graph_edges WHERE provenance LIKE '%local_llm_teacher%'")
        core.db.execute("DELETE FROM causal_edges WHERE provenance_source = 'local_llm_teacher'")
        core.logger.info("[OVERNIGHT] Старые факты от LLM удалены.")
    except Exception as e:
        core.logger.error(f"[OVERNIGHT] Ошибка очистки: {e}")

def _is_valid_query_word(word: str) -> bool:
    if len(word) < 3 or len(word) > 30: return False
    if not re.fullmatch(r'[а-яёА-ЯЁ\s]+', word): return False
    return True

def _is_noun(word: str) -> bool:
    w = word.lower().strip(".,!?():;\"'-")
    if w in FALSE_ADJECTIVES: return True
    for ending in ADJ_ENDINGS:
        if w.endswith(ending) and len(w) > len(ending) + 2: return False
    return True

def _clean_llm_response(text: str) -> str:
    patterns = [r"^Привет[!\.]?\s*", r"^Привет! 👋\s*", r"^Здравствуйте[!\.]?\s*"]
    for pat in patterns: text = re.sub(pat, "", text, count=1).lstrip()
    return text.strip()


def _format_log_block(text: str, max_chars: int = 33000) -> str:
    if text is None:
        return ""
    text = str(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _build_next_prompt(core, already_asked_session: set) -> Optional[str]:
    import random
    unknown_candidates = []
    try:
        rows = core.db.fetchall("SELECT node_id FROM graph_nodes WHERE node_type != 'axiom' ORDER BY lamport_tick ASC LIMIT 500")
        for (node_id,) in rows:
            if not _is_valid_query_word(node_id): continue
            if node_id.lower() in STOP_QUERY_WORDS: continue
            if not _is_noun(node_id): continue
            if node_id.lower() in already_asked_session: continue
            if _is_already_asked(core, node_id): already_asked_session.add(node_id.lower()); continue
            norm_id = normalize(node_id)
            belief_rows = core.db.fetchall("SELECT 1 FROM graph_edges WHERE source_node_id = ? OR target_node_id = ? LIMIT 1", (norm_id, norm_id))
            if not belief_rows: unknown_candidates.append(node_id)
    except Exception: pass
    if unknown_candidates and random.random() < 0.7:
        word = random.choice(unknown_candidates)
        return f"Дай определение понятия \"{word}\" и перечисли его основные свойства. Отвечай строго по делу, без приветствий и вводных фраз."
    return None

def _check_fact_quality(fact: dict) -> list:
    issues = []
    subject = (fact.get("subject") or "").lower()
    if subject in PRONOUN_SUBJECTS: issues.append("MISTAKEN_PRONOUN_SUBJECT")
    if " и " in subject: issues.append("MERGED_COMPOUND_SUBJECT")
    if subject in ADVERB_SUBJECTS: issues.append("ADVERB_AS_SUBJECT")
    return issues

def run_overnight_learning_session(core, max_iterations=500, max_duration_minutes=480,
                                   stop_event: Optional[threading.Event] = None,
                                   log_callback: Optional[Callable[[str], None]] = None):
    def log(msg: str):
        if log_callback: log_callback(msg)

    start_time = datetime.now()
    deadline = start_time + timedelta(minutes=max_duration_minutes)
    iteration, error_count, empty_response_streak, total_facts_learned = 0, 0, 0, 0
    already_asked_session = set()
    _ensure_asked_table(core)

    log_path = f"logs/overnight_learning_{datetime.now():%Y%m%d_%H%M}.log"
    logger = open(log_path, "a", encoding="utf-8")
    header = f"=== Ночной цикл обучения ===\nСтарт: {start_time}\nМакс. итераций: {max_iterations}\nМакс. длительность: {max_duration_minutes} мин.\n\n"
    logger.write(header); log(header)
    log("🧹 Очистка старых фактов от LLM...\n"); _purge_llm_facts(core)
    core.set_teaching_mode(True)

    try:
        while iteration < max_iterations and datetime.now() < deadline:
            if stop_event and stop_event.is_set():
                log("⏹️ Обучение остановлено пользователем.\n"); logger.write("⏹️ Обучение остановлено пользователем.\n"); break
            iteration += 1
            facts_this_iteration = 0
            try:
                prompt = _build_next_prompt(core, already_asked_session)
                if prompt is None: log("⚠️ Нет новых понятий для запроса.\n"); break

                # Извлекаем запрашиваемое слово из промта и помечаем как спрошенное
                asked_word = None
                match = re.search(r'понятия "(.+?)"', prompt)
                if match: asked_word = match.group(1).lower()
                if not asked_word:
                    m2 = re.search(r'Расскажи подробно о (\S+)', prompt)
                    if m2:
                        asked_word = m2.group(1).lower().rstrip(".,!?;:–-")
                        if asked_word.endswith(":"):
                            asked_word = asked_word.rstrip(":")
                if asked_word:
                    already_asked_session.add(asked_word)
                    _mark_as_asked(core, asked_word)

                msg = f"--- Итерация {iteration} ---\nПромпт: {prompt[:200]}\n"; logger.write(msg); log(msg)
                llm_reply = _ask_lm_studio(prompt)
                if not llm_reply:
                    msg = "⚠️ Пустой ответ от LM Studio\n"; logger.write(msg); log(msg)
                    empty_response_streak += 1
                    if empty_response_streak >= MAX_EMPTY_RESPONSES_IN_ROW:
                        msg = "❌ Прерывание: 10 пустых ответов подряд — LM Studio недоступна\n"; logger.write(msg); log(msg); break
                    time.sleep(2); continue
                else: empty_response_streak = 0
                llm_reply = _clean_llm_response(llm_reply)
                if not llm_reply: msg = "⚠️ Ответ очистился в пустую строку\n"; logger.write(msg); log(msg); continue
                msg = f"LM Studio: {_format_log_block(llm_reply)}\n"; logger.write(msg); log(msg)
                core._last_statement = None
                echo_response = core.generate_response(llm_reply)
                msg = f"Echo: {_format_log_block(echo_response)}\n"; logger.write(msg); log(msg)
                if hasattr(core.knowledge_extractor, 'extract_all'):
                    extracted_facts = core.knowledge_extractor.extract_all(llm_reply)
                    facts_this_iteration = len(extracted_facts); total_facts_learned += facts_this_iteration
                    if facts_this_iteration > 0: msg = f"📊 Фактов за итерацию: {facts_this_iteration}\n"; logger.write(msg); log(msg)
                if core.dialogue_controller.pending_teach.is_active():
                    core.dialogue_controller.pending_teach.cancel(); logger.write("⚠️ Ожидание PendingTeach сброшено\n")
                if core._last_statement:
                    issues = _check_fact_quality(core._last_statement)
                    if issues: msg = f"⚠️ Проблемы факта: {issues}\n"; logger.write(msg); log(msg)
            except Exception as e:
                error_count += 1; msg = f"❌ Ошибка на итерации {iteration}: {e}\n"; logger.write(msg); log(msg); continue
            time.sleep(1)
    finally:
        core.set_teaching_mode(False)
        duration = datetime.now() - start_time
        summary = f"\n=== ИТОГ ===\nИтераций: {iteration}, ошибок: {error_count}, фактов: {total_facts_learned}, пустых ответов подряд: {empty_response_streak}, время: {duration}\n"
        logger.write(summary); log(summary); logger.close()
        log(f"Ночной цикл завершён. Лог сохранён в {log_path}\n")

def _ask_lm_studio(prompt: str) -> Optional[str]:
    try:
        response = _post_json(LM_STUDIO_URL, payload={
            "messages": [{"role": "system", "content": "Ты — строгий учитель энциклопедии. Отвечай кратко, по делу. Без приветствий и вводных фраз. Сразу давай определение и перечисляй свойства."},
                         {"role": "user", "content": prompt}],
            "temperature": 0.7, "max_tokens": 32768}, timeout=180)
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices", [])
            if not choices: return None
            message = choices[0].get("message", {})
            content = message.get("content", "").strip()
            if not content: content = message.get("reasoning_content", "").strip()
            return content if content else None
        else: print(f"LM Studio error: {response.status_code}"); return None
    except Exception as e: print(f"Ошибка связи с LM Studio: {e}"); return None