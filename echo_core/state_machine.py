"""
State Transition Engine — детерминированные правила перехода состояний.
Выполняется главным потоком после каждого значимого события.
"""
from typing import Optional, Callable
from echo_core.self_state import SelfState


# Тип: функция, принимающая SelfState и словарь события, возвращающая предложение изменений или None
TransitionRule = Callable[[SelfState, dict], Optional[dict]]


class StateMachine:
    def __init__(self):
        self.rules: list[tuple[int, TransitionRule]] = []
        self._register_rules()

    def _register_rules(self):
        # Правила упорядочены по приоритету: чем меньше число, тем выше приоритет
        # Каждое правило возвращает словарь предложения или None

        def rule_critical(state: SelfState, event: dict) -> Optional[dict]:
            if event.get("type") == "emergency":
                return {"cognitive": {"mode": "analytical"}}
            return None

        def rule_stable(state: SelfState, event: dict) -> Optional[dict]:
            if event.get("type") == "calm_down" and state.cognitive.mode != "stable":
                if state.cognitive.internal_conflicts["exploration_vs_stability"] < 0.4:
                    return {"cognitive": {"mode": "stable"}}
            return None

        def rule_analytical(state: SelfState, event: dict) -> Optional[dict]:
            if state.cognitive.mode == "stable":
                if event.get("type") == "complex_question":
                    return {"cognitive": {"mode": "analytical"}}
            return None

        def rule_curious(state: SelfState, event: dict) -> Optional[dict]:
            if state.personality.curiosity > 0.7 and state.cognitive.mode in ("stable", "analytical"):
                if event.get("type") == "idle" and state.resources.tokens_per_sec > 10:
                    return {"cognitive": {"mode": "curious"}}
            return None

        self.rules = [
            (0, rule_critical),   # CRITICAL
            (1, rule_stable),     # STABLE
            (2, rule_analytical), # ANALYTICAL
            (3, rule_curious),    # CURIOUS
        ]

    def evaluate(self, state: SelfState, event: dict) -> Optional[dict]:
        """
        Прогоняет события через правила.
        Возвращает первое сработавшее предложение изменений (с наивысшим приоритетом).
        """
        for _, rule in sorted(self.rules, key=lambda x: x[0]):
            proposal = rule(state, event)
            if proposal is not None:
                return proposal
        return None