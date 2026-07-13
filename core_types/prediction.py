# echo_core/core_types/prediction.py
"""
Prediction — предсказание о будущем состоянии или событии.
Создаётся Hypothesis Engine на основе наблюдений и правил.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class Prediction:
    # Что предсказывается (субъект)
    subject: str

    # Тип отношения
    relation: str

    # Ожидаемое значение (объект)
    expected_value: str

    # Уверенность в предсказании
    confidence: float = 0.5

    # На чём основано (ID гипотезы, правила, наблюдения)
    based_on: List[str] = field(default_factory=list)

    # Временной горизонт: immediate, short_term, long_term
    time_horizon: str = "short_term"

    # Когда предсказание сделано
    created_at: Optional[str] = None

    # Статус исполнения: pending, confirmed, rejected, expired
    status: str = "pending"

    # Когда проверено
    verified_at: Optional[str] = None

    # Дополнительные метаданные
    metadata: Dict[str, Any] = field(default_factory=dict)

    def confirm(self) -> None:
        """Подтверждает предсказание."""
        self.status = "confirmed"

    def reject(self) -> None:
        """Отклоняет предсказание."""
        self.status = "rejected"

    def is_expired(self, current_time: str) -> bool:
        """Проверяет, не истекло ли время предсказания."""
        return self.status == "pending" and self.created_at is not None and self.created_at < current_time

    def summary(self) -> str:
        """Краткое описание для отладки."""
        return f"[{self.status}] {self.subject} {self.relation} {self.expected_value} (conf={self.confidence}, horizon={self.time_horizon})"