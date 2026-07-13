# echo_core/conflict.py
"""
Conflict — модель логического конфликта между двумя убеждениями.
Используется BeliefManager для отслеживания противоречий.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class Conflict:
    belief_a_id: int          # ID доминирующего убеждения
    belief_b_id: int          # ID атакующего/противоречащего убеждения
    conflict_type: str = "logical_opposition"
    resolution_status: str = "pending"  # pending, resolved_a, resolved_b, compromise
    id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "belief_a_id": self.belief_a_id,
            "belief_b_id": self.belief_b_id,
            "conflict_type": self.conflict_type,
            "resolution_status": self.resolution_status,
        }