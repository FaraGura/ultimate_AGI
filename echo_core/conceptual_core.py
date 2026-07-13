# echo_core/conceptual_core.py
"""
Conceptual Core v2.0 — извлечение смысла (аффордансов) из текста.
Превращает текст эпизода в Event Frame: actor, action, object, effect, context.
Опирается на Language Kernel и опциональный dependency parser (spaCy).
Без LLM. Детерминирован.
"""

import re
from typing import Optional, Dict, Any, List

from utils.utils_logger import get_logger


class ConceptualCore:
    def __init__(self, db, use_spacy: bool = True):
        """
        :param db: DatabaseManager с методами fetchone, fetchall.
        :param use_spacy: пытаться загрузить spaCy для точного разбора предложений.
        """
        self.logger = get_logger("ConceptualCore")
        self.db = db
        self.nlp = None

        # Загружаем Language Kernel в память (словари symbol/action/state)
        self.kernel_symbols = self._load_kernel_nodes("symbol")
        self.kernel_actions = self._load_kernel_nodes("action")
        self.kernel_states  = self._load_kernel_nodes("state")

        if use_spacy:
            self._init_spacy()

        self.logger.info(f"ConceptualCore v2.0 инициализирован (symbols: {len(self.kernel_symbols)}, "
                         f"actions: {len(self.kernel_actions)}, states: {len(self.kernel_states)}, "
                         f"spaCy: {self.nlp is not None})")

    # ------------------------------------------------------------
    # Загрузка Language Kernel из graph_nodes
    # ------------------------------------------------------------
    def _load_kernel_nodes(self, node_type: str) -> Dict[str, str]:
        """Возвращает словарь {слово: node_id} из graph_nodes."""
        rows = self.db.fetchall(
            "SELECT node_id, payload FROM graph_nodes WHERE node_type = ? AND provenance_source = 'tabula_rasa_language'",
            (node_type,)
        )
        result = {}
        import json
        for node_id, payload_blob in rows:
            try:
                payload = json.loads(payload_blob) if isinstance(payload_blob, str) else json.loads(payload_blob.decode("utf-8"))
                value = payload.get("value", "").strip().lower()
                if value:
                    result[value] = node_id
            except Exception:
                pass
        return result

    # ------------------------------------------------------------
    # Опциональный dependency parser (spaCy)
    # ------------------------------------------------------------
    def _init_spacy(self):
        try:
            import spacy
            self.nlp = spacy.load("ru_core_news_sm")
            self.logger.info("spaCy загружен (ru_core_news_sm)")
        except Exception:
            self.logger.warning("spaCy не загружен — работаем по позиционным правилам")

    # ------------------------------------------------------------
    # Главный метод: извлечение Event Frame
    # ------------------------------------------------------------
    def extract_event_frame(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Принимает сырой текст эпизода.
        Возвращает словарь Event Frame или None, если ничего не извлечено.
        """
        if not text or not text.strip():
            return None

        text = text.strip()
        frame = {
            "actor": None,
            "action": None,
            "object": None,
            "effect": None,
            "context": text[:200],  # сохраняем фрагмент исходного текста
            "importance": 0.5,
            "confidence": 0.3,  # начальная уверенность
        }

        # --- Попытка 1: dependency parser (spaCy) ---
        if self.nlp:
            parsed = self._parse_with_spacy(text)
            if parsed:
                frame.update(parsed)
                frame["confidence"] = 0.6  # выше, т.к. разбор точнее
                return frame

        # --- Попытка 2: позиционные правила ---
        parsed = self._parse_with_rules(text)
        if parsed:
            frame.update(parsed)
            frame["confidence"] = 0.4
            return frame

        # --- Ничего не извлекли ---
        return None

    # ------------------------------------------------------------
    # Разбор через spaCy (dependency parsing)
    # ------------------------------------------------------------
    def _parse_with_spacy(self, text: str) -> Optional[Dict[str, str]]:
        doc = self.nlp(text)
        actor = None
        action = None
        obj = None

        for token in doc:
            if token.dep_ == "nsubj" and not actor:
                actor = token.text
            elif token.dep_ == "ROOT" and token.pos_ == "VERB" and not action:
                action = token.lemma_  # лемма глагола
            elif token.dep_ in ("obj", "obl") and not obj:
                obj = token.text

        if not actor and not action:
            return None

        # Сверяем с Language Kernel
        result = {}
        if actor and actor.lower() in self.kernel_symbols:
            result["actor"] = actor
        elif actor:
            result["actor"] = actor  # даже если нет в kernel, сохраняем как есть

        if action and action.lower() in self.kernel_actions:
            result["action"] = action
        elif action:
            result["action"] = action

        if obj and obj.lower() in self.kernel_symbols:
            result["object"] = obj
        elif obj:
            result["object"] = obj

        return result if result else None

    # ------------------------------------------------------------
    # Позиционные правила (fallback без spaCy)
    # ------------------------------------------------------------
    def _parse_with_rules(self, text: str) -> Optional[Dict[str, str]]:
        words = [w.strip(".,!?():;\"'-") for w in text.split()]
        if len(words) < 2:
            return None

        # Ищем действие (глагол) среди слов, сравнивая с Language Kernel actions
        action_idx = None
        for i, w in enumerate(words):
            if w.lower() in self.kernel_actions:
                action_idx = i
                break

        if action_idx is None:
            return None

        result = {"action": words[action_idx]}

        # Субъект — слово перед действием (если есть)
        if action_idx > 0:
            candidate = words[action_idx - 1]
            if candidate.lower() in self.kernel_symbols or len(candidate) > 1:
                result["actor"] = candidate

        # Объект — слово после действия (если есть)
        if action_idx < len(words) - 1:
            candidate = words[action_idx + 1]
            if candidate.lower() in self.kernel_symbols or len(candidate) > 1:
                result["object"] = candidate

        return result


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock
    import json

    # Мокаем БД с Language Kernel
    kernel_nodes = [
        ("symbol_self", "symbol", json.dumps({"value": "я"})),
        ("symbol_other", "symbol", json.dumps({"value": "ты"})),
        ("symbol_object", "symbol", json.dumps({"value": "объект"})),
        ("act_create", "action", json.dumps({"value": "создавать"})),
        ("act_change", "action", json.dumps({"value": "изменять"})),
        ("act_delete", "action", json.dumps({"value": "удалять"})),
    ]

    mock_db = Mock()
    mock_db.fetchall.side_effect = lambda query, params: (
        [row for row in kernel_nodes if row[1] == params[0]]
        if "graph_nodes" in query else []
    )

    cc = ConceptualCore(mock_db, use_spacy=False)

    # Тест 1: извлечение с действием из kernel
    frame = cc.extract_event_frame("я создавать объект")
    assert frame is not None
    assert frame["action"] == "создавать"
    assert frame["actor"] == "я"
    assert frame["object"] == "объект"
    print("✅ Тест 1 пройден (kernel action)")

    # Тест 2: нет действия — None
    frame = cc.extract_event_frame("просто текст без глаголов")
    assert frame is None
    print("✅ Тест 2 пройден (нет действия)")

    # Тест 3: действие без субъекта и объекта
    frame = cc.extract_event_frame("изменять что-то")
    assert frame is not None
    assert frame["action"] == "изменять"
    print("✅ Тест 3 пройден (только действие)")

    print("\n🔥 Все тесты ConceptualCore v2.0 пройдены.")