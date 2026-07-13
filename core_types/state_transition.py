# echo_core/core_types/state_transition.py
"""
StateTransition — модель перехода объекта из одного состояния в другое.
Описывает причину, условия и результат изменения.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class StateTransition:
    # Какой объект меняет состояние
    object_id: str

    # Состояние ДО перехода
    before_state: str

    # Состояние ПОСЛЕ перехода
    after_state: str

    # Что вызвало переход (идентификатор события или описание)
    cause: Optional[str] = None

    # Условия, необходимые для перехода
    conditions: List[str] = field(default_factory=list)

    # Уверенность в том, что переход произойдёт при данных условиях
    confidence: float = 0.5

    # Источник знания о переходе (observation, rule, axiom)
    source: str = "observation"

    # Временная метка или идентификатор события-источника
    timestamp: Optional[str] = None

    # Дополнительные свойства
    properties: Dict[str, Any] = field(default_factory=dict)

    def is_applicable(self, current_state: str, context: Dict[str, Any]) -> bool:
        """Проверяет, применим ли переход в данном контексте."""
        if current_state != self.before_state:
            return False
        for condition in self.conditions:
            if condition not in context:
                return False
        return True

    def summary(self) -> str:
        """Краткое описание для отладки."""
        return f"{self.object_id}: {self.before_state} → {self.after_state} (причина: {self.cause or 'неизвестна'})"