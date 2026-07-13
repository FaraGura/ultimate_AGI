# echo_core/curiosity_engine.py
"""
Curiosity Engine v1.0.
Анализирует CausalGraph после каждого ответа пользователя.
Если у обсуждаемого концепта менее 3 связей — с вероятностью 30-40%
задаёт встречный вопрос для заполнения слепой зоны.
После ответа пользователя запускает микро-кристаллизацию.
"""
import random
import time
from typing import Optional, List
from utils.utils_logger import get_logger

class CuriosityEngine:
    def __init__(self, causal_graph, crystallization_engine, embedder, db):
        self.causal = causal_graph
        self.crystallization = crystallization_engine
        self.embedder = embedder
        self.db = db
        self.logger = get_logger("Curiosity")
        # Порог: меньше этого числа связей — концепт считается слабо изученным
        self.min_edges = 3
        # Вероятность задать вопрос (30-40%)
        self.question_probability = 0.35
        # Частота упоминаний концептов в последних диалогах (recency)
        self.recency = {}

    def analyse_and_ask(self, user_text: str, response_text: str = "") -> Optional[str]:
        """
        Возвращает вопрос, если обнаружен пробел в знаниях и сработала вероятность.
        Иначе None.
        """
        # Извлекаем потенциальные концепты из запроса пользователя
        concepts = self._extract_concepts(user_text)
        if not concepts:
            return None

        # Проверяем, у какого концепта меньше всего связей в графе
        best_concept = None
        best_edge_count = float('inf')
        for concept in concepts:
            edge_count = self._count_edges(concept)
            # Учитываем recency: если концепт недавно упоминался, повышаем приоритет
            recency_bonus = self.recency.get(concept, 0) * 0.5
            effective_edges = edge_count - recency_bonus
            if effective_edges < best_edge_count and edge_count < self.min_edges:
                best_edge_count = edge_count
                best_concept = concept

        if not best_concept:
            return None

        # Обновляем recency
        for concept in concepts:
            self.recency[concept] = self.recency.get(concept, 0) + 1
        # Чистим старые записи (больше 20)
        if len(self.recency) > 20:
            oldest = min(self.recency, key=self.recency.get)
            del self.recency[oldest]

        # Вероятностный предохранитель
        if random.random() > self.question_probability:
            return None

        # Формируем вопрос
        question = self._generate_question(best_concept)
        self.logger.info(f"Curiosity: задаю вопрос о '{best_concept}' (рёбер: {best_edge_count})")
        return question

    def micro_crystallize(self, concept: str, user_answer: str):
        """
        Микро-кристаллизация: извлекает закон из ответа пользователя
        и добавляет ребро в CausalGraph.
        """
        self.logger.info(f"Микро-кристаллизация концепта '{concept}' из ответа пользователя")
        # Используем существующий CrystallizationEngine для одного параграфа
        try:
            # Вызываем внутренний метод извлечения закона через Qwen (или LM Studio)
            law = self.crystallization._extract_law_with_qwen(user_answer)
            if law and law.get("core_essence"):
                # Добавляем связь в граф
                source = concept
                target = law.get("core_essence", "")[:50]
                if source and target:
                    self.causal.add_edge(source, target, "correlation", confidence=0.5)
                    self.logger.info(f"Добавлено ребро: {source} → {target}")
        except Exception as e:
            self.logger.error(f"Ошибка микро-кристаллизации: {e}")

    def _extract_concepts(self, text: str) -> List[str]:
        """Извлекает потенциальные концепты из текста (упрощённо)."""
        # Убираем стоп-слова и короткие слова, возвращаем уникальные
        stop_words = {"что", "это", "как", "для", "если", "потому", "когда", "тогда", "меня", "тебя",
                      "хочу", "может", "нужно", "надо", "буду", "есть", "быть", "просто", "ещё", "уже"}
        words = [w.strip(".,!?():;\"'-") for w in text.lower().split()
                 if len(w.strip(".,!?():;\"'-")) > 3 and w.strip(".,!?():;\"'-") not in stop_words]
        return list(set(words))[:5]

    def _count_edges(self, concept: str) -> int:
        """Считает количество рёбер в CausalGraph, связанных с концептом."""
        row = self.db.fetchone(
            "SELECT COUNT(*) FROM causal_edges WHERE source_concept = ? OR target_concept = ?",
            (concept, concept)
        )
        return row[0] if row else 0

    def _generate_question(self, concept: str) -> str:
        """Генерирует вопрос на основе шаблона (в будущем — через LLM)."""
        templates = [
            f"Я заметила пробел в понимании «{concept}». Что ты об этом думаешь?",
            f"В моей модели мира мало связей для «{concept}». Можешь объяснить?",
            f"Мне не хватает данных о «{concept}». Расскажи подробнее?",
        ]
        return random.choice(templates)

    def compose_unknown_word_question(self, word: str) -> str:
        """
        Активное обучение: вопрос о незнакомом слове.
        Детерминированный (без вероятностного гейта) — должен срабатывать всегда,
        когда обнаружено genuinely неизвестное слово.
        """
        return f"Я не знаю, что значит «{word}». Можешь объяснить мне, что это?"


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock

    # Мокаем зависимости
    mock_causal = Mock()
    mock_crystallization = Mock()
    mock_embedder = Mock()
    mock_db = Mock()

    # Настраиваем mock_db для возврата 2 рёбер (меньше порога 3)
    mock_db.fetchone.return_value = (2,)

    engine = CuriosityEngine(mock_causal, mock_crystallization, mock_embedder, mock_db)
    engine.question_probability = 1.0  # чтобы гарантированно сработал

    # Тест 1: Обнаружен пробел — должен быть вопрос
    question = engine.analyse_and_ask("Расскажи о квантовой физике")
    assert question is not None, "Вопрос не задан при пробеле в знаниях"
    assert "квантовой" in question.lower() or "физике" in question.lower(), f"Вопрос не содержит концепт: {question}"
    print("✅ Тест 1 (обнаружен пробел) пройден")

    # Тест 2: Нет пробела — вопрос не задаётся
    mock_db.fetchone.return_value = (10,)  # больше порога
    question = engine.analyse_and_ask("Как дела?")
    assert question is None, "Вопрос задан без пробела в знаниях"
    print("✅ Тест 2 (нет пробела — нет вопроса) пройден")

    # Тест 3: Микро-кристаллизация вызывает _extract_law_with_qwen
    engine.micro_crystallize("тест", "Это пример ответа.")
    assert mock_crystallization._extract_law_with_qwen.called, "Микро-кристаллизация не вызвала извлечение закона"
    print("✅ Тест 3 (микро-кристаллизация) пройден")

    print("\n🔥 Все тесты Curiosity Engine пройдены.")