# runtime/working_memory.py
"""
Working Memory v1.0 — временная оперативная память Эхо.
Живёт только во время сессии, не хранится в SQLite.
Жизненный цикл: CREATED → ACTIVE → SUSPENDED → CLEARED.
"""

from enum import Enum


class WMState(Enum):
    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLEARED = "cleared"


class WorkingMemory:
    def __init__(self):
        self.state = WMState.CREATED
        self.current_topic = None
        self.active_goal = None
        self.conversation_context = []
        self.temporary_hypothesis = []
        self.assumptions = []
        self.last_error = None

    def activate(self):
        self.state = WMState.ACTIVE

    def suspend(self):
        self.state = WMState.SUSPENDED

    def resume(self):
        if self.state == WMState.SUSPENDED:
            self.state = WMState.ACTIVE

    def clear(self):
        self.state = WMState.CLEARED
        self.current_topic = None
        self.active_goal = None
        self.conversation_context = []
        self.temporary_hypothesis = []
        self.assumptions = []
        self.last_error = None

    def set_topic(self, topic: str):
        self.current_topic = topic
        self.conversation_context.append(f"topic:{topic}")

    def set_goal(self, goal: str):
        self.active_goal = goal

    def add_hypothesis(self, hypothesis: str):
        self.temporary_hypothesis.append(hypothesis)

    def add_assumption(self, assumption: str):
        self.assumptions.append(assumption)

    def record_error(self, error: str):
        self.last_error = error

    def snapshot(self) -> dict:
        return {
            "state": self.state.value,
            "current_topic": self.current_topic,
            "active_goal": self.active_goal,
            "conversation_context": self.conversation_context[-5:],
            "temporary_hypothesis": self.temporary_hypothesis[-5:],
            "assumptions": self.assumptions[-5:],
            "last_error": self.last_error,
        }


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    wm = WorkingMemory()
    assert wm.state == WMState.CREATED

    wm.activate()
    assert wm.state == WMState.ACTIVE

    wm.set_topic("тестовая тема")
    assert wm.current_topic == "тестовая тема"

    wm.add_hypothesis("предположение")
    assert len(wm.temporary_hypothesis) == 1

    wm.suspend()
    assert wm.state == WMState.SUSPENDED

    wm.resume()
    assert wm.state == WMState.ACTIVE

    snap = wm.snapshot()
    assert "тестовая тема" in snap["current_topic"]

    wm.clear()
    assert wm.state == WMState.CLEARED
    assert wm.current_topic is None

    print("🔥 Все тесты WorkingMemory пройдены.")