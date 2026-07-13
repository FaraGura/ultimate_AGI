# echo_core/belief.py
"""
Belief — атомарная единица знания.
Может использоваться как обёртка над словарём или как самостоятельный объект.
Совместим с текущим форматом graph_edges.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Belief:
    source: str
    target: str
    relation: str
    confidence: float = 1.0
    certainty_type: str = "deductive"  # deductive, inductive, analogical, enthymeme, manual
    status: str = "created"            # created, candidate, active, conflicted, superseded, rejected
    id: Optional[int] = None
    quantifier: str = "all"            # all, some, none
    provenance: Dict[str, Any] = field(default_factory=lambda: {
        "engine": "manual",
        "parents": []
    })
    context_flags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Преобразует в словарь (формат graph_edges)."""
        result = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "confidence": self.confidence,
            "certainty_type": self.certainty_type,
            "status": self.status,
            "quantifier": self.quantifier,
            "provenance": self.provenance,
            "context_flags": self.context_flags,
        }
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Belief':
        """Создаёт Belief из словаря."""
        return cls(
            id=data.get("id"),
            source=data.get("source", ""),
            target=data.get("target", ""),
            relation=data.get("relation", ""),
            confidence=data.get("confidence", 1.0),
            certainty_type=data.get("certainty_type", "deductive"),
            status=data.get("status", "created"),
            quantifier=data.get("quantifier", "all"),
            provenance=data.get("provenance", {"engine": "manual", "parents": []}),
            context_flags=data.get("context_flags", {}),
        )