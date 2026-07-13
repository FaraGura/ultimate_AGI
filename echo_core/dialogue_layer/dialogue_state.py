# echo_core/dialogue_layer/dialogue_state.py
"""
Dialogue State v1.1
Хранит текущее ожидание Echo (какого ответа она ждёт),
незавершённую гипотезу (pending belief) и историю последних эпизодов.
v1.1: Защита от перезаписи, поддержка суб-диалогов через suspend/resume.
"""
from typing import Optional, List, Dict, Any
from collections import deque
from enum import Enum


class ExpectationType(Enum):
    CONFIRMATION = "CONFIRMATION"
    DENIAL = "DENIAL"
    ANSWER = "ANSWER"
    NONE = "NONE"


class DialogueState:
    def __init__(self):
        self.expectation: Optional[ExpectationType] = None
        self.pending_belief: Optional[Dict[str, Any]] = None
        self._suspended: Optional[Dict[str, Any]] = None  # Сохранённый контекст при ветвлении
        self.history: deque = deque(maxlen=5)

    def set_expectation(self, expectation_type: ExpectationType, belief: Dict[str, Any] = None):
        """Устанавливает ожидание. Если уже есть pending — вытесняет его в suspended."""
        if self.pending_belief is not None:
            self._suspended = {
                "expectation": self.expectation,
                "belief": self.pending_belief
            }
        self.expectation = expectation_type
        self.pending_belief = belief

    def clear_expectation(self):
        """Сбрасывает ожидание. Если был приостановленный контекст — восстанавливает."""
        self.expectation = None
        self.pending_belief = None
        if self._suspended:
            self.expectation = self._suspended["expectation"]
            self.pending_belief = self._suspended["belief"]
            self._suspended = None

    def has_suspended(self) -> bool:
        """Проверяет, есть ли приостановленный контекст (суб-диалог)."""
        return self._suspended is not None

    def record_episode(self, episode: Dict[str, Any]):
        """Сохраняет эпизод в историю."""
        self.history.append(episode)

    def get_last_episodes(self, count: int = 5) -> List[Dict[str, Any]]:
        """Возвращает последние N эпизодов."""
        return list(self.history)[-count:]

    def has_pending(self) -> bool:
        """Проверяет, есть ли незавершённая гипотеза."""
        return self.pending_belief is not None


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    state = DialogueState()

    # Тест 1: Установка ожидания
    state.set_expectation(ExpectationType.CONFIRMATION, {"source": "echo", "target": "name", "value": "Echo"})
    assert state.expectation == ExpectationType.CONFIRMATION
    assert state.pending_belief["value"] == "Echo"
    print("✅ Тест 1 (установка ожидания) пройден")

    # Тест 2: Защита от перезаписи (суб-диалог)
    state.set_expectation(ExpectationType.ANSWER, {"question": "Почему ты спрашиваешь?"})
    assert state.expectation == ExpectationType.ANSWER
    assert state.has_suspended()  # Предыдущий контекст сохранён
    print("✅ Тест 2 (защита от перезаписи) пройден")

    # Тест 3: Восстановление после сброса
    state.clear_expectation()
    assert state.expectation == ExpectationType.CONFIRMATION
    assert not state.has_suspended()  # Восстановлено, suspended очищен
    print("✅ Тест 3 (восстановление контекста) пройден")

    # Тест 4: История эпизодов
    for i in range(7):
        state.record_episode({"id": i, "text": f"Эпизод {i}"})
    assert len(state.get_last_episodes()) == 5
    print("✅ Тест 4 (история эпизодов) пройден")

    print("\n🔥 Все тесты DialogueState v1.1 пройдены.")