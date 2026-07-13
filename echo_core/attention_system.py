# echo_core/attention_system.py
"""
Attention System v1.0 — механизм фокусировки на релевантном контексте.
Выбирает из всей памяти только те факты, которые относятся к текущему запросу.
"""
from typing import Dict, List, Optional, Set
from collections import defaultdict
from utils.utils_logger import get_logger


class AttentionSystem:
    def __init__(self, causal_graph, episodic_memory, memory_manager):
        self.causal = causal_graph
        self.episodic = episodic_memory
        self.memory = memory_manager
        self.logger = get_logger("Attention")
        # Максимальное количество фактов в фокусе
        self.max_focus_size = 10
        # Порог релевантности
        self.relevance_threshold = 0.3

    def focus(self, query: str, context: Optional[List[str]] = None) -> Dict:
        """
        Определяет релевантный контекст для запроса.
        Возвращает словарь с отфильтрованными фактами и эпизодами.
        """
        if not context:
            context = []

        # 1. Извлекаем ключевые концепты из запроса
        query_concepts = self._extract_concepts(query)
        all_concepts = set(query_concepts + context)

        # 2. Собираем факты из графа, связанные с ключевыми концептами
        relevant_facts = self._collect_relevant_facts(all_concepts)

        # 3. Собираем связанные эпизоды
        relevant_episodes = self._collect_relevant_episodes(all_concepts)

        # 4. Ранжируем по релевантности и обрезаем до лимита
        ranked_facts = self._rank_by_relevance(relevant_facts, all_concepts)
        ranked_episodes = self._rank_episodes(relevant_episodes, all_concepts)

        return {
            "focus_concepts": list(all_concepts)[:5],
            "facts": ranked_facts[:self.max_focus_size],
            "episodes": ranked_episodes[:3],
        }

    def _extract_concepts(self, text: str) -> List[str]:
        """
        Извлекает ключевые концепты из текста запроса.
        """
        if not text or not text.strip():
            return []

        words = text.lower().split()
        stop_words = {
            "что", "как", "где", "когда", "почему", "зачем", "кто",
            "это", "для", "если", "потому", "тогда", "меня", "тебя",
            "хочу", "может", "нужно", "надо", "буду", "есть", "быть",
            "просто", "ещё", "уже", "очень", "весь", "весьма", "все",
        }
        concepts = []
        for w in words:
            w_clean = w.strip(".,!?():;\"'-")
            if len(w_clean) > 3 and w_clean not in stop_words:
                concepts.append(w_clean)
        return concepts[:5]

    def _collect_relevant_facts(self, concepts: Set[str]) -> List[Dict]:
        """
        Собирает все факты из графа, связанные с заданными концептами.
        """
        all_facts = []
        for concept in concepts:
            facts = self.causal.find_facts_about(concept)
            if facts:
                all_facts.extend(facts)
        return all_facts

    def _collect_relevant_episodes(self, concepts: Set[str]) -> List[Dict]:
        """
        Собирает эпизоды, связанные с заданными концептами.
        """
        all_episodes = []
        for concept in concepts:
            episodes = self.episodic.search(concept, limit=5)
            if episodes:
                all_episodes.extend(episodes)
        return all_episodes

    def _rank_by_relevance(self, facts: List[Dict], focus_concepts: Set[str]) -> List[Dict]:
        """
        Ранжирует факты по релевантности к фокусным концептам.
        """
        scored = []
        for fact in facts:
            score = 0
            source = fact.get("source", "").lower()
            target = fact.get("target", "").lower()
            relation = fact.get("relation", "").lower()

            # Повышаем score за совпадение с фокусными концептами
            for concept in focus_concepts:
                concept_lower = concept.lower()
                if concept_lower in source or source in concept_lower:
                    score += 3
                if concept_lower in target or target in concept_lower:
                    score += 3
                if concept_lower in relation or relation in concept_lower:
                    score += 1

            # Повышаем score за высокую уверенность
            confidence = fact.get("confidence", 0.5)
            score += confidence * 2

            scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored]

    def _rank_episodes(self, episodes: List[Dict], focus_concepts: Set[str]) -> List[Dict]:
        """
        Ранжирует эпизоды по релевантности.
        """
        scored = []
        for ep in episodes:
            score = 0
            user_text = ep.get("user_text", "").lower()
            echo_response = ep.get("echo_response", "").lower()

            for concept in focus_concepts:
                concept_lower = concept.lower()
                if concept_lower in user_text:
                    score += 2
                if concept_lower in echo_response:
                    score += 2

            weight = ep.get("weight", 0.5)
            score += weight * 2

            scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored]

    def get_focus_summary(self, focus_result: Dict) -> str:
        """
        Возвращает человекочитаемую сводку текущего фокуса.
        """
        concepts = focus_result.get("focus_concepts", [])
        facts = focus_result.get("facts", [])
        episodes = focus_result.get("episodes", [])

        parts = []
        if concepts:
            parts.append(f"В фокусе: {', '.join(concepts)}")
        if facts:
            parts.append(f"Фактов: {len(facts)}")
        if episodes:
            parts.append(f"Эпизодов: {len(episodes)}")

        return "; ".join(parts) if parts else "Фокус пуст"