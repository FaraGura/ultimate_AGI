# echo_core/core_types/knowledge_record.py
"""
KnowledgeRecord — универсальная запись о знании в долговременной памяти.
Может быть фактом, правилом, принципом или наблюдением.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class KnowledgeRecord:
    # О чём знание (субъект)
    subject: str

    # Тип отношения (например, IS_A, HAS_PROPERTY, CAUSES)
    relation: str

    # С чем связан субъект (объект)
    object: str

    # Тип знания: observation, fact, rule, principle, axiom
    knowledge_type: str = "fact"

    # Уверенность (0.0 – 1.0)
    confidence: float = 0.5

    # Источник: user_teaching, core_law, inference, alter, external_db
    source_type: str = "user_teaching"

    # Человекочитаемое описание источника
    source_description: str = ""

    # Когда запись создана
    created_at: Optional[str] = None

    # Когда последний раз подтверждена
    last_verified: Optional[str] = None

    # Счётчик подтверждений
    verification_count: int = 0

    # Дополнительные метаданные
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_axiom(self) -> bool:
        """Является ли знание аксиомой (не подлежит пересмотру)."""
        return self.knowledge_type == "axiom"

    def is_reliable(self, threshold: float = 0.7) -> bool:
        """Можно ли считать знание надёжным."""
        return self.confidence >= threshold and self.knowledge_type in ("rule", "principle", "axiom")

    def summary(self) -> str:
        """Краткое описание для отладки."""
        return f"[{self.knowledge_type}] {self.subject} {self.relation} {self.object} (conf={self.confidence}, src={self.source_type})"