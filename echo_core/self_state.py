"""
SelfState — единственный источник истины для всех параметров агента.
Сериализуется в JSON, обновляется атомарно через очередь предложений.
"""
import json
import time
from threading import Lock
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class Personality:
    name: str = "Эхо"
    mood: str = "curious"
    energy: float = 1.0
    logic: float = 0.7
    creativity: float = 0.7
    stability: float = 0.6
    curiosity: float = 0.8
    valence: float = 0.0          # эмоциональная валентность

    def normalize(self):
        for attr in ["energy", "logic", "creativity", "stability", "curiosity", "valence"]:
            val = getattr(self, attr)
            setattr(self, attr, max(0.0, min(val, 1.0)))


@dataclass
class CognitiveState:
    mode: str = "stable"           # stable / analytical / exploratory / curious
    autonomy_index: float = 0.5    # изменено на 0.5 по требованию архитектора
    max_autonomy: float = 1.0      # изменено на 1.0
    autonomy_lock: bool = False
    last_confidence: float = 0.5
    internal_conflicts: Dict[str, float] = field(default_factory=lambda: {
        "exploration_vs_stability": 0.5,
        "logic_vs_creativity": 0.5,
        "memory_vs_adaptation": 0.5
    })


@dataclass
class SystemResources:
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    vram_used_gb: float = 0.0
    gpu_temp: float = 0.0
    tokens_per_sec: float = 0.0
    throttling: bool = False


@dataclass
class SelfState:
    personality: Personality = field(default_factory=Personality)
    cognitive: CognitiveState = field(default_factory=CognitiveState)
    resources: SystemResources = field(default_factory=SystemResources)
    active_goal_ids: List[int] = field(default_factory=list)
    focus_concept: Optional[str] = None
    last_update: float = field(default_factory=time.time)

    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def apply_proposal(self, proposal: dict):
        """Применяет предложение изменений от модуля. Выполняется главным потоком."""
        with self._lock:
            if "personality" in proposal:
                for k, v in proposal["personality"].items():
                    if hasattr(self.personality, k):
                        setattr(self.personality, k, v)
                self.personality.normalize()
            if "cognitive" in proposal:
                for k, v in proposal["cognitive"].items():
                    if hasattr(self.cognitive, k):
                        setattr(self.cognitive, k, v)
            if "resources" in proposal:
                for k, v in proposal["resources"].items():
                    if hasattr(self.resources, k):
                        setattr(self.resources, k, v)
            if "active_goal_ids" in proposal:
                self.active_goal_ids = proposal["active_goal_ids"]
            if "focus_concept" in proposal:
                self.focus_concept = proposal["focus_concept"]
            self.last_update = time.time()

    def snapshot(self) -> dict:
        """Возвращает неизменяемый снимок для чтения другими модулями."""
        return {
            "personality": asdict(self.personality),
            "cognitive": asdict(self.cognitive),
            "resources": asdict(self.resources),
            "active_goal_ids": list(self.active_goal_ids),
            "focus_concept": self.focus_concept,
            "last_update": self.last_update
        }

    def to_json(self) -> str:
        return json.dumps(self.snapshot(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        state = cls()
        state.personality = Personality(**data.get("personality", {}))
        state.cognitive = CognitiveState(**data.get("cognitive", {}))
        state.resources = SystemResources(**data.get("resources", {}))
        state.active_goal_ids = data.get("active_goal_ids", [])
        state.focus_concept = data.get("focus_concept")
        return state

    # --------------- Восстановленные методы весов личности ---------------
    def get_personality_weights(self) -> dict:
        """Возвращает текущие веса личности."""
        return {
            "energy": self.personality.energy,
            "logic": self.personality.logic,
            "creativity": self.personality.creativity,
            "stability": self.personality.stability,
            "curiosity": self.personality.curiosity,
        }

    def apply_weight_delta(self, changes: dict):
        """Применяет изменения весов от навыка или события."""
        for key, delta in changes.items():
            if hasattr(self.personality, key):
                current = getattr(self.personality, key)
                setattr(self.personality, key, max(0.0, min(current + delta, 1.0)))
        self.personality.normalize()

    def reset_personality_weights(self):
        """Сбрасывает веса к значениям по умолчанию."""
        self.personality.energy = 1.0
        self.personality.logic = 0.7
        self.personality.creativity = 0.7
        self.personality.stability = 0.6
        self.personality.curiosity = 0.8
        self.personality.mood = "curious"