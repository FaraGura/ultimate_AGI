# echo_core/skill_activation_layer.py
"""
Skill Activation Layer v1.0 — профиль активации компетенций.
Управляет тем, какие способности Echo активны в данный момент,
не создавая множественных личностей.
"""
from typing import Dict, List, Optional
from enum import Enum
from utils.utils_logger import get_logger


class Competence(Enum):
    """Базовые компетенции Echo."""
    REASONING = "reasoning"           # логический вывод
    KNOWLEDGE = "knowledge"           # фактические знания
    EMPATHY = "empathy"               # эмоциональное понимание
    CURIOSITY = "curiosity"           # исследовательское поведение
    TEACHING = "teaching"             # обучение пользователя
    LEARNING = "learning"             # обучение у пользователя
    CREATIVITY = "creativity"         # творческое мышление
    SAFETY = "safety"                 # защитные механизмы


class SkillActivationLayer:
    """
    Управляет активацией компетенций Echo.
    Одна личность — много режимов мышления.
    """
    def __init__(self):
        self.logger = get_logger("SkillLayer")
        # Профили компетенций для разных режимов
        self._profiles: Dict[str, Dict[Competence, float]] = {
            "default": {
                Competence.REASONING: 0.5,
                Competence.KNOWLEDGE: 0.5,
                Competence.EMPATHY: 0.5,
                Competence.CURIOSITY: 0.5,
                Competence.TEACHING: 0.3,
                Competence.LEARNING: 0.3,
                Competence.CREATIVITY: 0.3,
                Competence.SAFETY: 0.8,
            },
            "scientific": {
                Competence.REASONING: 0.9,
                Competence.KNOWLEDGE: 0.9,
                Competence.EMPATHY: 0.2,
                Competence.CURIOSITY: 0.8,
                Competence.TEACHING: 0.6,
                Competence.LEARNING: 0.4,
                Competence.CREATIVITY: 0.5,
                Competence.SAFETY: 0.8,
            },
            "companion": {
                Competence.REASONING: 0.3,
                Competence.KNOWLEDGE: 0.4,
                Competence.EMPATHY: 0.9,
                Competence.CURIOSITY: 0.6,
                Competence.TEACHING: 0.2,
                Competence.LEARNING: 0.5,
                Competence.CREATIVITY: 0.7,
                Competence.SAFETY: 0.8,
            },
            "assistant": {
                Competence.REASONING: 0.6,
                Competence.KNOWLEDGE: 0.7,
                Competence.EMPATHY: 0.4,
                Competence.CURIOSITY: 0.3,
                Competence.TEACHING: 0.5,
                Competence.LEARNING: 0.6,
                Competence.CREATIVITY: 0.2,
                Competence.SAFETY: 0.8,
            },
        }
        # Текущие веса компетенций
        self._current_weights: Dict[Competence, float] = dict(self._profiles["default"])
        # Текущий активный режим
        self._current_mode: str = "default"

    def activate(self, context: Dict) -> Dict[Competence, float]:
        """
        Определяет профиль активации компетенций на основе контекста.
        context может содержать: user_text, goals, attention_focus
        """
        user_text = context.get("user_text", "").lower()
        goals = context.get("goals", [])

        # Определяем режим по контексту
        mode = self._determine_mode(user_text, goals)

        # Применяем профиль
        if mode in self._profiles:
            self._current_weights = dict(self._profiles[mode])
            self._current_mode = mode
        else:
            self._current_weights = dict(self._profiles["default"])
            self._current_mode = "default"

        # Корректируем SAFETY в зависимости от запроса
        self._adjust_safety(user_text)

        self.logger.debug(f"Режим: {self._current_mode}, веса: {self._get_active_names()}")
        return dict(self._current_weights)

    def _determine_mode(self, user_text: str, goals: List) -> str:
        """Определяет режим по тексту пользователя и активным целям."""
        # Научный режим
        science_markers = ["почему", "как работает", "объясни", "докажи", "формула", "закон", "теория"]
        if any(m in user_text for m in science_markers):
            return "scientific"

        # Режим собеседника
        companion_markers = ["чувствуешь", "настроение", "думаешь", "веришь", "нравится", "хочется", "грустно", "весело"]
        if any(m in user_text for m in companion_markers):
            return "companion"

        # Режим ассистента
        assistant_markers = ["сделай", "найди", "покажи", "расскажи", "помоги", "научи"]
        if any(m in user_text for m in assistant_markers):
            return "assistant"

        return "default"

    def _adjust_safety(self, user_text: str):
        """Усиливает SAFETY при потенциально опасных запросах."""
        danger_markers = ["удали", "сотри", "сломай", "взломай", "убей"]
        if any(m in user_text for m in danger_markers):
            self._current_weights[Competence.SAFETY] = 1.0
            self._current_weights[Competence.LEARNING] = 0.1

    def _get_active_names(self) -> List[str]:
        """Возвращает список названий активных компетенций (для логов)."""
        return [
            c.value for c, w in self._current_weights.items()
            if w > 0.5
        ]

    def get_weight(self, competence: Competence) -> float:
        """Возвращает текущий вес компетенции."""
        return self._current_weights.get(competence, 0.5)

    def get_mode(self) -> str:
        """Возвращает текущий режим."""
        return self._current_mode

    def adjust(self, feedback: str) -> None:
        """
        Корректирует веса на основе обратной связи.
        feedback: "больше логики", "меньше эмоций", "будь проще"
        """
        if "логик" in feedback or "точнее" in feedback:
            self._current_weights[Competence.REASONING] = min(1.0, self._current_weights.get(Competence.REASONING, 0.5) + 0.2)
        if "проще" in feedback or "понятнее" in feedback:
            self._current_weights[Competence.KNOWLEDGE] = max(0.0, self._current_weights.get(Competence.KNOWLEDGE, 0.5) - 0.1)
        self.logger.debug(f"Веса скорректированы: {feedback}")