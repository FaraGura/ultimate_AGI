# echo_core/dialogue/pending_teach.py
import re
import time
from typing import Optional

MAX_QUESTION_DEPTH = 3

REFUSAL_REPLIES = {"не знаю", "незнаю", "нет", "не знаю.", "не знаю,", "отстань", "не хочу"}
CONFIRMATION_ONLY_REPLIES = {"да", "да.", "верно", "верно.", "угу", "ага"}


class PendingTeach:
    def __init__(self, knowledge_extractor, core):
        self.knowledge_extractor = knowledge_extractor
        self.core = core
        self._pending_concept: Optional[dict] = None
        self._question_depth: int = 0

    def is_active(self) -> bool:
        return self._pending_concept is not None

    def reset(self):
        """Сброс состояния – вызывается из ExpectationManager при подтверждении/отказе."""
        self._pending_concept = None
        self._question_depth = 0

    def cancel(self):
        """Принудительно сбрасывает ожидание объяснения (без возврата ответа)."""
        self._pending_concept = None
        self._question_depth = 0

    def start_teaching(self, concept: str) -> Optional[str]:
        """
        Запускает ожидание объяснения незнакомого слова. Возвращает
        готовый вопрос-уточнение. concept уже должен быть проверен
        вызывающей стороной как реально неизвестный.
        """
        self._pending_concept = {"concept": concept, "asked_at": time.time()}
        self._question_depth = 1
        return concept  # вопрос формирует curiosity_engine выше по цепочке

    def handle_response(self, user_text: str, act: str) -> Optional[str]:
        if not self._pending_concept:
            return None

        # Вопрос прерывает цепочку обучения — пусть обрабатывается обычным путём
        if act == "QUESTION" or user_text.strip().endswith("?"):
            self._pending_concept = None
            return None

        return self._process_teaching(user_text)

    def _process_teaching(self, user_text: str) -> str:
        concept = self._pending_concept.get("concept")
        reply_lower = user_text.lower().strip()
        is_refusal = reply_lower in REFUSAL_REPLIES
        is_confirmation_only = reply_lower in CONFIRMATION_ONLY_REPLIES
        self._pending_concept = None

        if is_refusal:
            self._question_depth = 0
            return "[DUL] Хорошо, не буду настаивать. Расскажешь, когда будешь готов."

        if is_confirmation_only:
            return "[DUL] Я ждала объяснение, а не подтверждение. Можешь описать словами?"

        if not concept:
            return "[DUL] Я ждала объяснение, а не подтверждение. Можешь описать словами?"

        if len(user_text.split()) > 15 and not re.search(
            r"это|значит|называется|имеет|является", user_text.lower()
        ):
            return "[DUL] Это слишком длинное объяснение. Попробуй короче, например 'X — это Y'."

        extracted = self.knowledge_extractor.extract(user_text)
        if extracted and self.core._is_valid_fact(extracted["subject"], extracted["object"]):
            self.core._last_statement = {
                "source": extracted["subject"],
                "target": extracted["object"],
                "relation": extracted["relation"],
            }
            return self._continue_or_finish(
                user_text,
                f"[DUL] Я запомнила: {extracted['subject']} "
                f"{extracted['relation']} {extracted['object']}."
            )

        captured = self.core._capture_object_teaching(concept, user_text)
        if captured:
            return self._continue_or_finish(
                user_text,
                f"[DUL] Спасибо, я запомнила: «{concept}» — это {user_text.strip()}."
            )

        return f"[DUL] Я не смогла сохранить объяснение «{concept}». Попробуй иначе?"

    def _continue_or_finish(self, user_text: str, base_response: str) -> str:
        """Проверяет глубину цепочки уточняющих вопросов и либо продолжает
        (спрашивая про следующее незнакомое слово), либо завершает."""
        if self._question_depth >= MAX_QUESTION_DEPTH:
            self._question_depth = 0
            return base_response

        new_unknown = self.core._extract_unknown_words(user_text)
        if new_unknown:
            next_concept = new_unknown[0]
            self._pending_concept = {"concept": next_concept, "asked_at": time.time()}
            self._question_depth += 1
            return f"{base_response} Но я не знаю, что значит «{next_concept}». Можешь объяснить?"

        self._question_depth = 0
        return base_response