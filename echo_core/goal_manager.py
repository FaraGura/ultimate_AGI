import time
import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Goal:
    goal_id: int
    description: str
    priority: int  # 0 = mission, 1 = strategic, 2 = tactical, 3 = operational
    energy_budget: float  # доля доступных ресурсов
    active: bool = True
    created_at: float = field(default_factory=time.time)
    completed: bool = False


class GoalManager:
    def __init__(self):
        self.goals: List[Goal] = []
        self._id_counter = 0
        self._register_default_goals()

    def _register_default_goals(self):
        self.add_goal("Самосохранение (целостность БД и модулей)", priority=0, energy_budget=0.2)
        self.add_goal("Выполнение запроса пользователя", priority=0, energy_budget=0.5)
        self.add_goal("Обнаружение и устранение противоречий в знаниях", priority=1, energy_budget=0.15)
        self.add_goal("Любопытство: поиск новых концептов", priority=2, energy_budget=0.1)
        self.add_goal("Проверка гипотетических связей", priority=3, energy_budget=0.05)

    def add_goal(self, description: str, priority: int = 3, energy_budget: float = 0.1) -> int:
        g = Goal(goal_id=self._id_counter, description=description, priority=priority, energy_budget=energy_budget)
        self.goals.append(g)
        self._id_counter += 1
        return g.goal_id

    def get_active_goals(self) -> List[Goal]:
        return [g for g in self.goals if g.active and not g.completed]

    def allocate_energy(self, total_available: float) -> dict:
        """Распределяет энергетический бюджет по активным целям."""
        active = self.get_active_goals()
        if not active:
            return {}
        # Сортировка по приоритету (0 — высший)
        active.sort(key=lambda g: g.priority)
        allocation = {}
        remaining = total_available
        for goal in active:
            if remaining <= 0:
                break
            alloc = min(goal.energy_budget * total_available, remaining)
            allocation[goal.goal_id] = alloc
            remaining -= alloc
        return allocation

    def complete_goal(self, goal_id: int):
        for g in self.goals:
            if g.goal_id == goal_id:
                g.completed = True
                g.active = False
                break

    def curiosity_signal(self, prediction_error: float, confidence_threshold: float = 0.3) -> Optional[int]:
        """Если ошибка предсказания высока, активирует цель 'Любопытство'."""
        if prediction_error > confidence_threshold:
            for g in self.goals:
                if "Любопытство" in g.description and not g.active:
                    g.active = True
                    return g.goal_id
        return None