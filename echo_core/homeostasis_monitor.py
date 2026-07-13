# echo_core/homeostasis_monitor.py
"""
Мониторинг системных ресурсов (psutil, pynvml) с EfficiencyIndex —
динамическим порогом молчания на основе продуктивности обучения.
Логика: чем МЕНЬШЕ новых рёбер в CausalGraph, тем НИЖЕ порог молчания
(Эхо становится разговорчивее, чтобы заполнить пробелы).
"""
import time
import threading
from datetime import datetime
from utils.utils_logger import get_logger

try:
    import psutil
except ImportError:
    psutil = None

try:
    from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetTemperature, nvmlShutdown
except ImportError:
    nvmlInit = None


class HomeostasisMonitor:
    def __init__(self):
        self.logger = get_logger("Homeostasis")
        self.tokens_per_sec = 0.0
        self.tps_history = []
        self._stop = False

        self.silence_threshold = 0.7
        self.last_efficiency_check = 0.0
        self.causal_graph_ref = None

        if psutil is None:
            self.logger.warning("psutil недоступен, мониторинг CPU/RAM отключён.")
        if nvmlInit:
            try:
                nvmlInit()
                self.gpu_handle = nvmlDeviceGetHandleByIndex(0)
            except Exception:
                self.gpu_handle = None
        else:
            self.gpu_handle = None

    def set_causal_graph(self, causal_graph):
        self.causal_graph_ref = causal_graph

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop:
            try:
                if psutil:
                    cpu = psutil.cpu_percent(interval=1)
                    ram = psutil.virtual_memory().used / (1024**3)
                    self.logger.debug(f"CPU: {cpu}%, RAM: {ram:.2f}GB")
                if self.gpu_handle:
                    mem = nvmlDeviceGetMemoryInfo(self.gpu_handle)
                    temp = nvmlDeviceGetTemperature(self.gpu_handle, 0)
                    self.logger.debug(f"VRAM: {mem.used/1024**2:.0f}MB, Temp: {temp}C")
            except Exception as e:
                self.logger.error(f"Ошибка мониторинга: {e}")
            time.sleep(5)

    def update_tps(self, tps: float):
        self.tokens_per_sec = tps
        self.tps_history.append(tps)
        if len(self.tps_history) > 100:
            self.tps_history.pop(0)

    def is_throttling(self, threshold_factor=0.5) -> bool:
        if len(self.tps_history) < 10:
            return False
        avg = sum(self.tps_history) / len(self.tps_history)
        return self.tokens_per_sec < avg * threshold_factor

    def get_state(self) -> dict:
        return {
            "tps": self.tokens_per_sec,
            "throttling": self.is_throttling(),
            "silence_threshold": self.silence_threshold,
        }

    def compute_efficiency(self) -> float:
        if not self.causal_graph_ref:
            return self.silence_threshold

        now = time.time()
        if now - self.last_efficiency_check < 60:
            return self.silence_threshold

        cutoff = datetime.fromtimestamp(now - 600).isoformat()
        row = self.causal_graph_ref.db.fetchone(
            "SELECT COUNT(*) FROM causal_edges WHERE last_updated > ?",
            (cutoff,)
        )
        new_edges = row[0] if row else 0

        stress = 1.0 if self.is_throttling() else 0.5
        efficiency = new_edges / max(1, new_edges + stress)
        self.silence_threshold = max(0.3, min(0.9, 0.9 - efficiency * 0.5))

        self.last_efficiency_check = now
        self.logger.debug(f"EfficiencyIndex: new_edges={new_edges}, efficiency={efficiency:.2f}, silence_threshold={self.silence_threshold:.2f}")
        return self.silence_threshold

    def stop(self):
        self._stop = True
        if nvmlInit and self.gpu_handle:
            nvmlShutdown()


if __name__ == "__main__":
    from unittest.mock import Mock

    monitor = HomeostasisMonitor()

    initial = monitor.silence_threshold
    result = monitor.compute_efficiency()
    assert result == initial
    print("✅ Тест 1 (без causal_graph) пройден")

    mock_graph = Mock()
    mock_graph.db = Mock()
    monitor.set_causal_graph(mock_graph)

    monitor.last_efficiency_check = 0
    mock_graph.db.fetchone.return_value = (10,)
    monitor.is_throttling = lambda: False
    result = monitor.compute_efficiency()
    assert result > 0.7
    print(f"✅ Тест 2 (активное обучение, порог={result:.2f}) пройден")

    monitor.last_efficiency_check = 0
    mock_graph.db.fetchone.return_value = (0,)
    result = monitor.compute_efficiency()
    assert result < 0.7
    print(f"✅ Тест 3 (нет обучения, порог={result:.2f}) пройден")

    print("\n🔥 Все тесты HomeostasisMonitor пройдены.")