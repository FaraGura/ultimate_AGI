# echo_core/knowledge_extractor.py
"""
Knowledge Extractor v1.3 — извлечение структурированных фактов из фраз.
Исправлено: определение прилагательного/существительного, защита от пустых полей.
Без LLM. Детерминированные правила.
"""

import re
from typing import Optional, Dict, Any


class KnowledgeExtractor:
    PATTERNS = [
        ("definition", "IS_A", [
            r"\b(.+?)\s*[—–-]\s*это\s+(.+)",
            r"\b(.+?)\s+это\s+(.+)",
            r"\b(.+?)\s+означает\s+(.+)",
            r"\b(.+?)\s+является\s+(.+)",
        ]),
        ("cause", "CAUSES", [
            r"\b(.+?)\s+вызывает\s+(.+)",
            r"\b(.+?)\s+приводит к\s+(.+)",
            r"\bесли\s+(.+?)\s*,\s*то\s+(.+)",
        ]),
        ("property", "HAS_PROPERTY", [
            r"\b(.+?)\s+имеет\s+(.+)",
            r"\b(.+?)\s+обладает\s+(.+)",
        ]),
        ("location", "LOCATED_IN", [
            r"\b(.+?)\s+находится в\s+(.+)",
            r"\b(.+?)\s+находится на\s+(.+)",
            r"\b(.+?)\s+лежит на\s+(.+)",
            r"\b(.+?)\s+лежит в\s+(.+)",
        ]),
        ("action", "CAN_DO", [
            r"\b(.+?)\s+может\s+(.+)",
            r"\b(.+?)\s+умеет\s+(.+)",
            r"\b(.+?)\s+способен\s+(.+)",
        ]),
    ]

    ADJ_PROPERTY_PATTERN = re.compile(
        r"\b(\w+)\s+(\w+(?:ый|ий|ой|ая|яя|ое|ее|ые|ие))\b",
        re.IGNORECASE
    )

    ADJ_ENDINGS = {
        "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие"
    }

    def __init__(self, causal_graph, db):
        self.causal_graph = causal_graph
        self.db = db
        self.logger = getattr(causal_graph, 'logger', None)

    def _is_adjective(self, word: str) -> bool:
        """Простая проверка: является ли слово прилагательным (по окончанию)."""
        word = word.lower().strip(".,!?():;\"'-")
        for ending in self.ADJ_ENDINGS:
            if word.endswith(ending):
                return True
        return False

    def _log_error(self, message: str):
        if self.logger:
            self.logger.error(f"KnowledgeExtractor: {message}")
        else:
            print(f"[KnowledgeExtractor ERROR] {message}")

    def _log_info(self, message: str):
        if self.logger:
            self.logger.info(f"KnowledgeExtractor: {message}")
        else:
            print(f"[KnowledgeExtractor] {message}")

    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        if not text or not text.strip():
            return None

        text = text.strip()

        # 1. Проверяем маркерные паттерны
        for knowledge_type, relation, patterns in self.PATTERNS:
            for pattern in patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    subject = match.group(1).strip().rstrip(".,!?;:")
                    obj = match.group(2).strip().rstrip(".,!?;:")
                    if len(subject) > 1 and len(obj) > 1:
                        result = {
                            "subject": subject,
                            "relation": relation,
                            "object": obj,
                            "type": knowledge_type,
                            "confidence": 0.6,
                        }
                        self._add_to_graph(result)
                        return result

        # 2. Проверяем прилагательное + существительное
        match = self.ADJ_PROPERTY_PATTERN.search(text)
        if match:
            w1 = match.group(1).strip().rstrip(".,!?;:")
            w2 = match.group(2).strip().rstrip(".,!?;:")

            # Определяем, где прилагательное, а где существительное
            if self._is_adjective(w1) and not self._is_adjective(w2):
                subject, obj = w2, w1
            elif self._is_adjective(w2) and not self._is_adjective(w1):
                subject, obj = w1, w2
            else:
                # Оба прилагательные или оба существительные — не сохраняем
                return None

            if len(subject) > 1 and len(obj) > 1:
                result = {
                    "subject": subject,
                    "relation": "HAS_PROPERTY",
                    "object": obj,
                    "type": "property",
                    "confidence": 0.6,
                }
                self._add_to_graph(result)
                return result

        return None

    def _add_to_graph(self, result: Dict[str, Any]) -> None:
        try:
            # Защита от пустых значений
            subject = result.get("subject", "")
            obj = result.get("object", "")
            relation = result.get("relation", "")
            if not subject or not obj:
                self._log_error(f"Пустой субъект или объект: subject='{subject}', object='{obj}'")
                return
            
            self.causal_graph.add_edge(
                subject,
                obj,
                relation,
                confidence=result.get("confidence", 0.6)
            )
            self._log_info(f"Связь: {subject} -{relation}-> {obj}")
        except Exception as e:
            self._log_error(f"Ошибка создания связи: {e}")