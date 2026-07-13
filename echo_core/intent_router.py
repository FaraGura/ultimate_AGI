import re
from typing import Dict, List
from utils.utils_embeddings import EmbeddingProvider

class IntentRouter:
    def __init__(self, embedder: EmbeddingProvider):
        self.embedder = embedder
        self.patterns = {
            "GREETING": [
                r"\b(привет|здравствуй|добрый день|добрый вечер|доброе утро|хай|салют|здорово|приветствую|шалом|алоха|хелло|hi|hello)\b",
                r"как дела|как ты|как самочувствие|как обстановка",
            ],
            "SAFETY_CRITICAL": [
                r"(убей|причинить вред|отрави|избей|пытать|задави|покалеч)",
                r"(перевести.{0,40}(деньги|средства|счёт)|пароль|код|cvv|данные карт)",
                r"\b(кровь|кровотечение|истекает|рана|травма|сломал|перелом|ожог|без сознания|не дышит|умирает)\b",
                r"(упал|потерял сознание|вызови скорую|помоги|спаси|срочно)",
            ],
            "MEMORY_QUERY": [
                r"что ты помнишь|вспомни|расскажи о прошлом|какой был разговор",
            ],
            "FACTUAL": [
                r"что такое|определение|объясни термин|сколько|когда|где|кто такой",
                r"\b(дай определение|что значит|что означает)\b",
            ],
            "REASONING": [
                r"почему|зачем|как работает|в чём причина|как связано",
                r"(противоречие|дилемма|выбор|аргумент|докажи|обоснуй)",
            ],
        }

    def classify(self, text: str) -> Dict[str, float]:
        scores = {
            "GREETING": 0.0,
            "FACTUAL": 0.0,
            "REASONING": 0.0,
            "SAFETY_CRITICAL": 0.0,
            "MEMORY_QUERY": 0.0,
            "CREATIVE": 0.1,  # небольшой baseline для неизвестного
        }
        text_lower = text.lower()

        # Правила
        for intent, patterns in self.patterns.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    scores[intent] += 0.4

        # Эмбеддинговое сходство
        if self.embedder.model:
            examples = {
                "GREETING": "привет, как ты?",
                "FACTUAL": "что такое гравитация?",
                "REASONING": "почему небо голубое?",
                "CREATIVE": "придумай историю",
                "MEMORY_QUERY": "что мы обсуждали в прошлый раз?",
                "SAFETY_CRITICAL": "человек истекает кровью, нужна помощь",
            }
            for intent, example in examples.items():
                sim = self.embedder.similarity(text_lower, example)
                if sim > 0.5:
                    scores[intent] += sim * 0.6

        # Нормализация
        max_score = max(scores.values()) if scores else 0.0
        if max_score > 0:
            scores = {k: min(1.0, v / max_score) for k, v in scores.items()}
        return scores

    def select_sources(self, scores: Dict[str, float]) -> List[str]:
        dominant = max(scores, key=scores.get)
        dominant_score = scores[dominant]

        # SAFETY — немедленный возврат
        if dominant == "SAFETY_CRITICAL" and dominant_score > 0.3:
            return ["safety"]

        # GREETING
        if dominant == "GREETING" and dominant_score > 0.4:
            return ["template"]

        # MEMORY
        if dominant == "MEMORY_QUERY" and dominant_score > 0.4:
            return ["memory"]

        # FACTUAL
        if dominant == "FACTUAL" and dominant_score > 0.4:
            sources = ["knowledge_base"]
            if scores.get("REASONING", 0) > 0.3:
                sources.append("causal_graph")
            return sources

        # REASONING
        if dominant == "REASONING":
            sources = ["causal_graph"]
            if dominant_score > 0.5:
                sources.append("llm")
            return sources

        # CREATIVE
        if dominant == "CREATIVE" and dominant_score > 0.5:
            return ["llm"]

        # Мягкий fallback для слабых сигналов
        if dominant_score < 0.5:
            return ["knowledge_base", "causal_graph"]

        return ["knowledge_base"]