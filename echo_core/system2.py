import time
from typing import Dict, Optional
from utils.utils_logger import get_logger
from .causal_graph import CausalGraph
from utils.utils_embeddings import EmbeddingProvider
from .style_engine import StyleEngine


class System2:
    def __init__(self, db, causal_graph: CausalGraph, embedder: EmbeddingProvider):
        self.db = db
        self.causal = causal_graph
        self.embedder = embedder
        self.logger = get_logger("System2")
        self.style_engine = StyleEngine()

    def verify(self, user_text: str, draft: str, state_snapshot: Dict, intent: str = "GENERAL") -> Dict:
        """
        Полная двухэтапная проверка:
        1. Causal Consistency
        2. Style Compliance
        Возвращает {"valid": bool, "score": float, "warnings": list, "final_text": str}
        """
        warnings = []
        score = 1.0

        # --- Causal Consistency ---
        # Проверяем, что ответ не противоречит аксиомам и графу
        if not self._check_consistency(draft):
            warnings.append("Ответ может противоречить законам или аксиомам.")
            score -= 0.3

        # --- Style Compliance ---
        styled = self.style_engine.apply(draft, state_snapshot, intent)
        if styled != draft:
            # Если стиль изменился, это не ошибка, просто применяем
            pass

        # Проверка на пустые штампы
        if "я как искусственный интеллект" in draft.lower() or "как языковая модель" in draft.lower():
            warnings.append("Ответ содержит запрещённые LLM-штампы.")
            score -= 0.5

        valid = len(warnings) == 0 and score > 0.5
        return {
            "valid": valid,
            "score": score,
            "warnings": warnings,
            "final_text": styled
        }

    def _check_consistency(self, text: str) -> bool:
        """
        Проверяет текст на соответствие аксиомам через Causal Graph.
        Пока упрощённо: если есть путь в графе от упомянутых концептов к аксиомам — ок.
        """
        # Заглушка: в будущем будет извлекать концепты из текста и искать противоречия
        return True  # Временно всегда True, пока граф не наполнен