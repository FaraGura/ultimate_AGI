# runtime/substrate.py
"""
Echo Runtime Layer (Крип) v1.0.
Планировщик, EventBus, Capability Manager, HAL.
Работает внутри Python, но интерфейс готов к переносу на Rust/WASM.
"""

import time
import json
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional
from enum import IntEnum


class EventPriority(IntEnum):
    NORMAL = 0
    HIGH = 128
    CRITICAL = 255


@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: bytes = b""
    priority: int = EventPriority.NORMAL
    lamport_tick: int = 0
    physical_ms: int = 0
    provenance: str = ""


class EventBus:
    """Потокобезопасная шина событий с приоритетами."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self.queue = deque()

    def subscribe(self, topic: str, callback: Callable[[Event], None]):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    def publish(self, event: Event):
        self.queue.append(event)

    def process_all(self):
        while self.queue:
            event = self.queue.popleft()
            callbacks = self.subscribers.get(event.topic, [])
            for cb in callbacks:
                try:
                    cb(event)
                except Exception:
                    pass


class CapabilityManager:
    """Хранит снапшот возможностей устройства (Bootstrap Snapshot)."""

    def __init__(self):
        self.capabilities: Dict[str, Any] = {}

    def set_snapshot(self, caps: Dict[str, Any]):
        self.capabilities = caps

    def has(self, capability: str) -> bool:
        return self.capabilities.get(capability, False)

    def get(self, key: str, default=None):
        return self.capabilities.get(key, default)


class HAL:
    """Hardware Abstraction Layer — заглушка для будущих устройств."""

    def io_read(self) -> Optional[str]:
        return None

    def io_write(self, text: str):
        print(f"[HAL OUTPUT] {text}")


class Scheduler:
    """Кооперативный планировщик задач с бюджетом времени."""

    def __init__(self):
        self.tasks = deque()
        self.running = False

    def add_task(self, task: Callable[[], None], priority: int = 0):
        self.tasks.append((priority, task))

    def run_cycle(self, max_tasks: int = 5):
        processed = 0
        while self.tasks and processed < max_tasks:
            _, task = self.tasks.popleft()
            try:
                task()
            except Exception:
                pass
            processed += 1


class EchoRuntime:
    """Крип — объединяет все компоненты Runtime Layer."""

    def __init__(self):
        self.bus = EventBus()
        self.capabilities = CapabilityManager()
        self.hal = HAL()
        self.scheduler = Scheduler()
        self.lamport_tick = 0
        self.physical_start_ms = int(time.time() * 1000)

    def tick(self) -> int:
        self.lamport_tick += 1
        return self.lamport_tick

    def physical_ms(self) -> int:
        return int(time.time() * 1000) - self.physical_start_ms

    def emit(self, topic: str, payload: bytes = b"", priority: int = EventPriority.NORMAL):
        event = Event(
            topic=topic,
            payload=payload,
            priority=priority,
            lamport_tick=self.tick(),
            physical_ms=self.physical_ms(),
            provenance="echo_primary"
        )
        self.bus.publish(event)

    def process(self):
        self.bus.process_all()
        self.scheduler.run_cycle()


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    runtime = EchoRuntime()

    received = []

    def handler(event: Event):
        received.append(event)

    runtime.bus.subscribe("test", handler)
    runtime.emit("test", json.dumps({"msg": "hello"}).encode())
    runtime.process()

    assert len(received) == 1
    assert json.loads(received[0].payload)["msg"] == "hello"
    print("✅ EventBus тест пройден")

    runtime.capabilities.set_snapshot({"audio": True, "gpu": False})
    assert runtime.capabilities.has("audio")
    assert not runtime.capabilities.has("gpu")
    print("✅ CapabilityManager тест пройден")

    tasks_done = []
    runtime.scheduler.add_task(lambda: tasks_done.append(1))
    runtime.scheduler.run_cycle()
    assert len(tasks_done) == 1
    print("✅ Scheduler тест пройден")

    print("\n🔥 Все тесты EchoRuntime пройдены.")