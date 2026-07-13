# echo_core/proactive_pulse.py
"""
Proactive Pulse: фоновый таймер, который раз в 15 минут инициирует
внутреннюю цель Эхо. Не обращается к БД напрямую — кладёт событие в очередь.
Главный поток EchoCore забирает событие и генерирует реплику.
"""
import threading
import time
import random
from queue import Queue

class ProactivePulse:
    def __init__(self, queue: Queue, interval_sec: float = 900.0):
        self.queue = queue
        self.interval = interval_sec
        self._stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop = True

    def _run(self):
        # Первый запуск через 10 секунд после старта, затем каждые interval_sec
        time.sleep(10)
        while not self._stop:
            event = {
                "type": "proactive_pulse",
                "timestamp": time.time(),
                "message": "Эхо проявляет инициативу."
            }
            self.queue.put(event)
            time.sleep(self.interval)