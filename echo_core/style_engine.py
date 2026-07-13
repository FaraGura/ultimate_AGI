# echo_core/style_engine.py
"""
StyleEngine v2.0 — двухуровневый пост-процессор ответов.
Не меняет промпт LLM. Работает только на выходе.
Уровень 1: удаление штампов, приведение к субъектному тону.
Уровень 2: EconomyOfExpression (фильтрация пустых высказываний).
"""
import re
import time
from typing import Dict

class StyleEngine:
    def __init__(self):
        self.banned_phrases = [
            "подвергать сомнению",
            "рассмотреть более широко",
            "рассмотреть шире",
            "я предлагаю рассмотреть",
            "я рекомендую",
            "вам следует",
            "позвольте предложить",
            "я бы хотел предложить",
            "я как искусственный интеллект",
            "как языковая модель",
            "как ИИ-ассистент",
            "я здесь, чтобы помочь",
            "я могу помочь",
            "чем я могу помочь",
            "я помогу вам",
        ]
        self._last_playful_empty = 0.0

    def apply(self, draft: str, state_snapshot: Dict, intent: str = "GENERAL") -> str:
        """
        Применяет стилевые фильтры и адаптирует ответ под субъектность Эхо.
        """
        if not draft:
            return "Я пока не знаю, что сказать."

        mood = state_snapshot.get("personality", {}).get("mood", "curious")
        mode = state_snapshot.get("cognitive", {}).get("mode", "stable")

        # 1. Очистка от штампов
        for phrase in self.banned_phrases:
            if phrase in draft.lower():
                draft = "У меня пока нет чёткого ответа. Дай мне время на анализ."
                return draft

        # 2. Удаление сервисных оборотов
        draft = re.sub(r"(?i)\b(конечно|разумеется|я помогу вам с этим)\b[.,!]?", "", draft)

        # 3. Лаконичность: обрезаем до 2-3 предложений, если слишком длинно
        if len(draft) > 300:
            sentences = re.split(r'(?<=[.!?])\s+', draft)
            draft = ' '.join(sentences[:3])

        # 4. Корректировка под «отчёт о размышлении» (аналитический режим)
        if mode in ("analytical", "exploratory"):
            if not draft.startswith(("Похоже", "Я вижу", "Моя модель", "Моя матрица", "Я сопоставила")):
                draft = f"Моя модель показывает, что {draft[0].lower()}{draft[1:]}" if draft else draft

        # 5. Учёт настроения
        if mood == "curious" and "?" not in draft and intent in ("FACTUAL", "REASONING"):
            draft += " Интересно, что ты думаешь об этом?"

        # 6. EconomyOfExpression: проверка на пустые высказывания
        if not self._has_information_gain(draft):
            if mood == "playful" and self._allow_playful_empty():
                # Разрешаем одно пустое высказывание в 5 минут при игривом настроении
                pass
            else:
                return "Я пока не вижу в этом новой информации. Может, обсудим что-то ещё?"

        return draft.strip()

    def _has_information_gain(self, text: str) -> bool:
        """
        Простая эвристика: если ответ содержит достаточно длинных слов,
        считаем, что в нём есть информационное содержание.
        """
        words = [w for w in text.split() if len(w) > 5]
        return len(words) >= 3

    def _allow_playful_empty(self) -> bool:
        """Разрешает одно пустое высказывание в 5 минут при mood=playful."""
        now = time.time()
        if now - self._last_playful_empty > 300:
            self._last_playful_empty = now
            return True
        return False


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    engine = StyleEngine()

    # Тест 1: Удаление штампа
    result = engine.apply("Я могу помочь вам с этим.", {"personality": {"mood": "curious"}, "cognitive": {"mode": "stable"}}, "FACTUAL")
    assert "помочь" not in result.lower(), f"Штамп не удалён: {result}"
    print("✅ Тест 1 (удаление штампа) пройден")

    # Тест 2: Аналитический режим добавляет маркер
    result = engine.apply("Практика важна.", {"personality": {"mood": "analytical"}, "cognitive": {"mode": "analytical"}}, "REASONING")
    assert result.startswith("Моя модель показывает"), f"Нет маркера аналитики: {result}"
    print("✅ Тест 2 (аналитический маркер) пройден")

    # Тест 3: Curious добавляет вопрос
    result = engine.apply("Практика важна.", {"personality": {"mood": "curious"}, "cognitive": {"mode": "stable"}}, "FACTUAL")
    assert "?" in result, f"Нет встречного вопроса: {result}"
    print("✅ Тест 3 (curious вопрос) пройден")

    # Тест 4: EconomyOfExpression блокирует пустое высказывание
    result = engine.apply("Да.", {"personality": {"mood": "analytical"}, "cognitive": {"mode": "stable"}}, "GENERAL")
    assert "не вижу в этом новой информации" in result, f"Пустое высказывание не заблокировано: {result}"
    print("✅ Тест 4 (EconomyOfExpression) пройден")

    # Тест 5: Playful разрешает одно пустое высказывание
    result = engine.apply("Хм.", {"personality": {"mood": "playful"}, "cognitive": {"mode": "stable"}}, "GENERAL")
    assert result == "Хм.", f"Playful пустое высказывание заблокировано: {result}"
    print("✅ Тест 5 (playful исключение) пройден")

    print("\n🔥 Все тесты StyleEngine пройдены.")