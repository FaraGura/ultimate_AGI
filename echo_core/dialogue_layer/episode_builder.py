# echo_core/dialogue_layer/episode_builder.py
"""
Episode Builder v1.9
v1.9: Синхронизирован с SpeechAct v1.9.
"""
import re
from typing import Dict, Optional
from echo_core.dialogue_layer.speech_act import SpeechActClassifier
from echo_core.dialogue_layer.self_resolver import SelfResolver
from echo_core.dialogue_layer.dialogue_state import DialogueState, ExpectationType


class EpisodeBuilder:
    def __init__(self, state: DialogueState):
        self.speech_act = SpeechActClassifier()
        self.resolver = SelfResolver()
        self.state = state

    def build(self, user_text: str) -> Dict:
        act = self.speech_act.classify(user_text)
        focus = self.resolver.resolve_text(user_text)
        episode = None

        if self.state.has_pending():
            pending = self.state.pending_belief

            if act == "CORRECTION":
                new_value = self._extract_value(user_text)
                if new_value is None:
                    episode = {
                        "speaker": "USER", "listener": "SELF",
                        "speech_act": "DENIAL",
                        "concept": pending.get("concept"),
                        "value": pending.get("value"),
                        "confidence": max(0.1, pending.get("confidence", 0.5) - 0.3),
                        "needs_confirmation": False,
                        "provenance": {"source_module": "episode_builder", "certainty_type": "inductive"},
                    }
                    self.state.clear_expectation()
                    self.state.record_episode(episode)
                    return episode

                pending["value"] = new_value
                pending["confidence"] = 0.3
                episode = {
                    "speaker": "USER", "listener": "SELF",
                    "speech_act": "CORRECTION",
                    "concept": pending.get("concept"),
                    "value": new_value,
                    "confidence": 0.3,
                    "needs_confirmation": True,
                    "provenance": {"source_module": "episode_builder", "certainty_type": "inductive"},
                }
                self.state.set_expectation(ExpectationType.CONFIRMATION, pending)
                self.state.record_episode(episode)
                return episode

            if act == "CONFIRMATION":
                episode = {
                    "speaker": "USER", "listener": "SELF",
                    "speech_act": "CONFIRMATION",
                    "concept": pending.get("concept"),
                    "value": pending.get("value"),
                    "confidence": min(1.0, pending.get("confidence", 0.5) + 0.3),
                    "needs_confirmation": False,
                    "provenance": {"source_module": "episode_builder", "certainty_type": "inductive"},
                }
                self.state.clear_expectation()
                self.state.record_episode(episode)
                return episode

            elif act == "DENIAL":
                episode = {
                    "speaker": "USER", "listener": "SELF",
                    "speech_act": "DENIAL",
                    "concept": pending.get("concept"),
                    "value": pending.get("value"),
                    "confidence": max(0.1, pending.get("confidence", 0.5) - 0.3),
                    "needs_confirmation": False,
                    "provenance": {"source_module": "episode_builder", "certainty_type": "inductive"},
                }
                self.state.clear_expectation()
                self.state.record_episode(episode)
                return episode

        # Новый эпизод
        extracted_value = self._extract_value(user_text)
        episode = {
            "speaker": "USER", "listener": focus,
            "speech_act": act,
            "concept": self._extract_concept(user_text, act, focus),
            "value": extracted_value or user_text.strip(),
            "confidence": 0.3,
            "needs_confirmation": act in ("TEACHING", "CORRECTION", "UNKNOWN"),
            "provenance": {"source_module": "episode_builder", "certainty_type": "inductive"},
        }

        if act == "TEACHING" and focus == "SELF":
            if extracted_value and extracted_value != user_text.strip():
                self.state.set_expectation(
                    ExpectationType.CONFIRMATION,
                    {"concept": episode["concept"], "value": episode["value"], "confidence": episode["confidence"]}
                )

        self.state.record_episode(episode)
        return episode

    def _extract_value(self, text: str) -> Optional[str]:
        correction_match = re.search(r"не\s+.+?[,;]\s*а\s+(.+)$", text, re.IGNORECASE)
        if correction_match:
            return correction_match.group(1).strip().rstrip(".,!?;:")
        neg_match = re.match(r"^не\s+(\S+)$", text.strip(), re.IGNORECASE)
        if neg_match:
            return None
        markers = [
            "тебя зовут", "твоё имя", "твоя имя", "имя у тебя",
            "зовут", "называют", "кличка", "псевдоним", "погоняло",
            "твоим именем является", "ты являешься", "являешься",
            "называется", "это",
        ]
        lower = text.lower()
        for marker in markers:
            if marker in lower:
                idx = lower.rfind(marker)
                value = text[idx + len(marker):].strip().lstrip(" -:«»\"").strip()
                value = value.rstrip(".,!?;:")
                if value and value != marker:
                    return value
                return None
        return text.strip().rstrip(".,!?;:")

    def _extract_concept(self, text: str, act: str, focus: str) -> Optional[str]:
        if focus == "SELF":
            return "self_identity"
        if focus == "USER":
            return "user_identity"
        if act == "TEACHING":
            return "taught_concept"
        return "general_concept"


# ======================
if __name__ == "__main__":
    state = DialogueState()
    builder = EpisodeBuilder(state)
    ep = builder.build("Твоё имя Эхо")
    assert ep["value"] == "Эхо"
    ep = builder.build("да")
    assert ep["speech_act"] == "CONFIRMATION"
    print("✅ Все тесты EpisodeBuilder v1.9 пройдены.")