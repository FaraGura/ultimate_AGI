# echo_core/dialogue/dialogue_controller.py
"""
DialogueController — главный фасад Dialogue Domain.
Координирует ExpectationManager и PendingTeach. Не содержит собственной
бизнес-логики сверх диспетчеризации между ними — вся логика в дочерних
модулях, по контракту спецификации.
"""

from typing import Optional

from .expectation_manager import ExpectationManager
from .pending_teach import PendingTeach


class DialogueController:
    def __init__(self, dialogue_state, knowledge_extractor, core):
        self.expectation_manager = ExpectationManager(dialogue_state, core)
        self.pending_teach = PendingTeach(knowledge_extractor, core)

    def has_pending_expectation(self) -> bool:
        """Публичный доступ для echo_core — не читать dialogue_state напрямую."""
        return self.expectation_manager.has_pending()

    def handle_dialogue(self, user_text: str, episode: dict, act: str,
                         had_expectation: bool) -> Optional[str]:
        if had_expectation:
            response = self.expectation_manager.handle_user_act(act, episode)
            if response is not None:
                return response

        if self.pending_teach.is_active():
            response = self.pending_teach.handle_response(user_text, act)
            if response is not None:
                return response

        return None
