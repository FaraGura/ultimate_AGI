# echo_core/core_types/event_model.py
"""
EventModel — универсальное представление события в мире Echo.
Не зависит от текста, источника данных или модуля-обработчика.
Это язык, на котором говорят все когнитивные модули.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class EventModel:
    """
    Событие — это изменение состояния мира, а не просто предложение.
    Источником может быть текст, зрение, звук, лог, другой Альтер.
    """
    # Кто совершает действие (агент)
    agent: Optional[str] = None

    # Что делает агент (действие)
    action: Optional[str] = None

    # Над чем совершается действие (объект)
    object: Optional[str] = None

    # Где происходит событие (место)
    location: Optional[str] = None

    # Почему произошло (причина)
    cause: Optional[str] = None

    # К чему привело (результат/эффект)
    effect: Optional[str] = None

    # Состояние объекта ДО события
    before_state: Optional[str] = None

    # Состояние объекта ПОСЛЕ события
    after_state: Optional[str] = None

    # Кто или что создало это событие (источник данных)
    source: Optional[str] = None

    # Тип источника: text, vision, audio, alter, system
    source_type: str = "text"

    # Уверенность в событии (0.0 – 1.0)
    confidence: float = 0.5

    # Дополнительные свойства, специфичные для источника
    properties: Dict[str, Any] = field(default_factory=dict)

    # Связанные события (например, цепочка причин)
    related_events: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Проверяет, содержит ли событие минимально необходимые данные."""
        return self.action is not None and len(self.action.strip()) > 0

    def summary(self) -> str:
        """Краткое описание события для отладки."""
        parts = []
        if self.agent:
            parts.append(self.agent)
        if self.action:
            parts.append(self.action)
        if self.object:
            parts.append(self.object)
        return " ".join(parts) if parts else "пустое событие"