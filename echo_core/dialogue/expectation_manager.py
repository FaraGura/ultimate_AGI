# echo_core/dialogue/expectation_manager.py
from typing import Optional


class ExpectationManager:
    def __init__(self, dialogue_state, core):
        self.dialogue_state = dialogue_state
        self.core = core

    def has_pending(self) -> bool:
        return self.dialogue_state.has_pending()

    def set_expectation(self, expectation_type, belief) -> None:
        self.dialogue_state.set_expectation(expectation_type, belief)

    def clear_expectation(self) -> None:
        self.dialogue_state.clear_expectation()

    def handle_user_act(self, act: str, episode: dict) -> Optional[str]:
        if act == "CONFIRMATION":
            return self._on_confirmation(episode)
        if act == "DENIAL":
            return self._on_denial()
        return None

    def _on_confirmation(self, episode: dict) -> str:
        concept = episode.get("concept", "general_concept")
        value = episode.get("value")
        if self.dialogue_state.pending_belief:
            value = self.dialogue_state.pending_belief.get("value", value)

        self.core.confirmed_facts[concept] = value

        if concept == "self_identity" and value:
            self.core.belief_manager.receive({
                "source": "echo",
                "target": value,
                "relation": "HAS_NAME",
                "confidence": 0.9,
                "certainty_type": "inductive",
                "provenance": {"engine": "dul", "method": "teaching"},
            })
            self.core._save_self_identity(value)

        self.clear_expectation()
        # Вместо прямого обращения к core._pending_teach_concept/Question_depth
        # вызываем сброс состояния активного обучения через dialogue_controller
        if hasattr(self.core, 'dialogue_controller'):
            self.core.dialogue_controller.pending_teach.reset()
        return f"[DUL] Я запомнила: {concept} = {value}. Спасибо за подтверждение."

    def _on_denial(self) -> str:
        self.clear_expectation()
        if hasattr(self.core, 'dialogue_controller'):
            self.core.dialogue_controller.pending_teach.reset()
        return "[DUL] Поняла, я не буду сохранять это как верное. Можешь уточнить?"