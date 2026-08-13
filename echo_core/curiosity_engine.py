# echo_core/curiosity_engine.py
"""
Curiosity Engine v2.0 — детерминированное любопытство.
Задаёт вопросы при пробелах в знаниях, углубляет понимание вместо повторения.
"""
import random
import time
from typing import Optional, List, Dict, Set
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
        
        # История заданных вопросов: предотвращает повторы
        self.asked_questions: Set[str] = set()
        
        # Глубина понимания для каждого концепта: 0 = поверхностное, 3 = глубокое
        self.understanding_depth: Dict[str, int] = {}
        
        # Стоимость повторения вопроса (высокая для базовых вещей)
        self.high_cost_patterns = [
            "зовут", "имя", "кто ты", "что ты такое",
            "как тебя", "твоё имя"
        ]

    def _is_high_cost_question(self, concept: str) -> bool:
        """Проверяет, не является ли вопрос о концепте слишком базовым для повтора."""
        concept_lower = concept.lower()
        return any(pattern in concept_lower for pattern in self.high_cost_patterns)

    def _already_asked(self, concept: str) -> bool:
        """Проверяет, задавали ли мы уже вопрос об этом концепте."""
        return concept.lower() in self.asked_questions

    def _mark_asked(self, concept: str):
        """Помечает концепт как тот, о котором уже спрашивали."""
        self.asked_questions.add(concept.lower())

    def _get_understanding_depth(self, concept: str) -> int:
        """Возвращает текущую глубину понимания концепта."""
        return self.understanding_depth.get(concept.lower(), 0)

    def _increase_understanding(self, concept: str):
        """Увеличивает глубину понимания концепта."""
        key = concept.lower()
        self.understanding_depth[key] = self._get_understanding_depth(key) + 1

    def analyse_and_ask(self, user_text: str, response_text: str = "") -> Optional[str]:
        """
        Анализирует запрос пользователя и возвращает вопрос,
        если обнаружен пробел в знаниях.
        """
        concepts = self._extract_concepts(user_text)
        if not concepts:
            return None

        best_concept = None
        best_edge_count = float('inf')
        best_depth = -1

        for concept in concepts:
            edge_count = self._count_edges(concept)
            depth = self._get_understanding_depth(concept)
            
            # Ищем концепт с наименьшим количеством связей,
            # но приоритет отдаём тем, у кого меньше глубина понимания
            if edge_count < self.min_edges:
                if depth > best_depth or (depth == best_depth and edge_count < best_edge_count):
                    best_edge_count = edge_count
                    best_concept = concept
                    best_depth = depth

        if not best_concept:
            return None

        # Проверяем, не задавали ли мы уже этот вопрос
        if self._already_asked(best_concept):
            # Если уже спрашивали — задаём углубляющий вопрос
            if self._get_understanding_depth(best_concept) < 2:
                question = self._generate_deeper_question(best_concept)
                self._increase_understanding(best_concept)
                return question
            return None

        # Проверяем стоимость вопроса
        if self._is_high_cost_question(best_concept) and self._already_asked(best_concept):
            return None

        # Задаём вопрос
        self._mark_asked(best_concept)
        self._increase_understanding(best_concept)
        question = self._generate_question(best_concept)
        self.logger.info(f"Curiosity: задаю вопрос о '{best_concept}' (рёбер: {best_edge_count}, глубина: {self._get_understanding_depth(best_concept)})")
        return question

    def micro_crystallize(self, concept: str, user_answer: str):
        """Микро-кристаллизация: извлекает закон из ответа пользователя."""
        self.logger.info(f"Микро-кристаллизация концепта '{concept}' из ответа пользователя")
        try:
            law = self.crystallization._extract_law_with_qwen(user_answer)
            if law and law.get("core_essence"):
                source = concept
                target = law.get("core_essence", "")[:50]
                if source and target:
                    self.causal.add_edge(source, target, "correlation", confidence=0.5)
                    self.logger.info(f"Добавлено ребро: {source} → {target}")
        except Exception as e:
            self.logger.error(f"Ошибка микро-кристаллизации: {e}")

    def _extract_concepts(self, text: str) -> List[str]:
        """Извлекает потенциальные концепты из текста."""
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
        """Генерирует первый вопрос о концепте."""
        templates = [
            f"Я заметила пробел в понимании «{concept}». Что ты об этом думаешь?",
            f"В моей модели мира мало связей для «{concept}». Можешь объяснить?",
            f"Мне не хватает данных о «{concept}». Расскажи подробнее?",
        ]
        return random.choice(templates)

    def _generate_deeper_question(self, concept: str) -> str:
        """Генерирует углубляющий вопрос о концепте."""
        templates = [
            f"Я уже знаю кое-что о «{concept}», но хочу понять глубже. Почему это так работает?",
            f"О «{concept}» я уже слышала, но не понимаю причин. Почему это происходит?",
            f"Я помню про «{concept}», но как это связано с остальным миром?",
        ]
        return random.choice(templates)

    def compose_unknown_word_question(self, word: str) -> str:
        """
        Активное обучение: вопрос о незнакомом слове.
        Детерминированный — срабатывает всегда при обнаружении неизвестного слова.
        """
        return f"Я не знаю, что значит «{word}». Можешь объяснить мне, что это?"


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock

    mock_causal = Mock()
    mock_crystallization = Mock()
    mock_embedder = Mock()
    mock_db = Mock()

    mock_db.fetchone.return_value = (2,)

    engine = CuriosityEngine(mock_causal, mock_crystallization, mock_embedder, mock_db)

    # Тест 1: Обнаружен пробел — должен быть вопрос
    question = engine.analyse_and_ask("Расскажи о квантовой физике")
    assert question is not None, "Вопрос не задан при пробеле в знаниях"
    assert "квантовой" in question.lower() or "физике" in question.lower(), f"Вопрос не содержит концепт: {question}"
    print("✅ Тест 1 (обнаружен пробел) пройден")

    # Тест 2: Нет пробела — вопрос не задаётся
    mock_db.fetchone.return_value = (10,)
    question = engine.analyse_and_ask("Как дела?")
    assert question is None, "Вопрос задан без пробела в знаниях"
    print("✅ Тест 2 (нет пробела — нет вопроса) пройден")

    # Тест 3: Микро-кристаллизация вызывает _extract_law_with_qwen
    engine.micro_crystallize("тест", "Это пример ответа.")
    assert mock_crystallization._extract_law_with_qwen.called, "Микро-кристаллизация не вызвала извлечение закона"
    print("✅ Тест 3 (микро-кристаллизация) пройден")

    # Тест 4: Вопрос не повторяется для одного и того же концепта
    mock_db.fetchone.return_value = (2,)
    q1 = engine.analyse_and_ask("что такое квант?")
    assert q1 is not None, "Первый вопрос должен быть задан"
    q2 = engine.analyse_and_ask("что такое квант?")
    assert q2 is None or "уже знаю" in q2.lower(), f"Второй вопрос должен быть углубляющим, а не повторным: {q2}"
    print("✅ Тест 4 (нет повторов) пройден")

    # Тест 5: Высокая стоимость вопроса (имя) — не переспрашиваем
    engine.asked_questions.add("имя")
    question = engine.analyse_and_ask("как тебя зовут?")
    assert question is None, "Вопрос об имени не должен повторяться"
    print("✅ Тест 5 (высокая стоимость вопроса) пройден")

    print("\n🔥 Все тесты Curiosity Engine v2.0 пройдены.")