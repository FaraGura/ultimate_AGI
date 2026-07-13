import math
import time

def temporal_weight(created_at: float, half_life_days: float = 30.0) -> float:
    """
    Экспоненциальное затухание: вес = exp(-λ * age).
    Возраст в днях, half_life_days — период полураспада.
    """
    if created_at <= 0:
        return 1.0
    now = time.time()
    age_seconds = now - created_at
    age_days = age_seconds / 86400.0
    if age_days <= 0:
        return 1.0
    lam = math.log(2) / half_life_days
    return math.exp(-lam * age_days)