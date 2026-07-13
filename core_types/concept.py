# echo_core/core_types/concept.py
"""
Concept — универсальное представление объекта, идеи или явления в мире Echo.
Хранит свойства, аффордансы (возможные действия) и ограничения.
Не зависит от источника знаний.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Concept:
    """
    Концепт — это то, что Echo знает о чём-то.
    Например: "нож", "вода", "тяжесть", "радость".
    """
    # Уникальное имя концепта (ключ в графе)
    id: str

    # Человекочитаемое название
    name: str

    # Тип концепта: object, action, property, emotion, system
    concept_type: str = "object"

    # Свойства (цвет, вес, материал, агрегатное состояние)
    properties: Dict[str, Any] = field(default_factory=dict)

    # Аффордансы — что можно делать с этим концептом
    affordances: List[str] = field(default_factory=list)

    # Ограничения — что нельзя делать или при каких условиях
    constraints: List[str] = field(default_factory=list)

    # Родительские концепты (связи IS_A)
    parents: List[str] = field(default_factory=list)

    # Дочерние концепты (обратные связи IS_A)
    children: List[str] = field(default_factory=list)

    # Связанные концепты (другие типы связей)
    related: List[str] = field(default_factory=list)

    # Источник знания (откуда Echo это знает)
    source: str = "unknown"

    # Уверенность в знании
    confidence: float = 0.5

    def has_property(self, prop_name: str) -> bool:
        """Проверяет, есть ли у концепта указанное свойство."""
        return prop_name in self.properties

    def can_do(self, action: str) -> bool:
        """Проверяет, может ли концепт выполнить указанное действие."""
        return action in self.affordances

    def is_restricted_by(self, constraint: str) -> bool:
        """Проверяет, имеет ли концепт указанное ограничение."""
        return constraint in self.constraints

    def summary(self) -> str:
        """Краткое описание концепта для отладки."""
        return f"[{self.concept_type}] {self.name} (свойств: {len(self.properties)}, аффордансов: {len(self.affordances)})"