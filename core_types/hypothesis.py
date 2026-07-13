# echo_core/core_types/hypothesis.py
"""
Hypothesis — предположение, основанное на наблюдениях.
Может стать правилом при достаточном количестве подтверждений.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Hypothesis:
    # О чём гипотеза (субъект)
    subject: str

    # Тип отношения (например, CAUSES, HAS_PROPERTY, IS_A)
    relation: str

    # С чем связан субъект (объект)
    object: str

    # Статус: observation, hypothesis, rule, principle, rejected
    status: str = "hypothesis"

    # Уверенность (0.0 – 1.0)
    confidence: float = 0.3

    # Сколько наблюдений подтверждают
    evidence_count: int = 0

    # ID наблюдений, на которых основана
    observation_ids: List[str] = field(default_factory=list)

    # Когда создана
    created_at: Optional[str] = None

    # Когда последний раз обновлялась
    last_updated: Optional[str] = None

    # Почему отвергнута (если статус rejected)
    rejection_reason: Optional[str] = None

    def promote(self) -> None:
        """Повышает статус: observation → hypothesis → rule → principle."""
        if self.status == "observation":
            self.status = "hypothesis"
        elif self.status == "hypothesis":
            self.status = "rule"
        elif self.status == "rule":
            self.status = "principle"

    def reject(self, reason: str = "") -> None:
        """Отклоняет гипотезу."""
        self.status = "rejected"
        if reason:
            self.rejection_reason = reason

    def add_evidence(self, observation_id: str) -> None:
        """Добавляет подтверждающее наблюдение."""
        self.evidence_count += 1
        if observation_id not in self.observation_ids:
            self.observation_ids.append(observation_id)
        # Повышаем уверенность, но не выше 1.0
        self.confidence = min(1.0, self.confidence + 0.05)

    def summary(self) -> str:
        """Краткое описание для отладки."""
        return f"[{self.status}] {self.subject} {self.relation} {self.object} (conf={self.confidence}, evidence={self.evidence_count})"