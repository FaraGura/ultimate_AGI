# echo_core/episodic_memory.py
"""
Episodic Memory v1.0 — событийная память диалогов (Этап 1 ТЗ).

Запоминает каждый обмен как событие (user_text + echo_response), а не просто текст.
Поддержка:
- SQLite FTS5 полнотекстовый поиск (с fallback на LIKE).
- ACT-R decay: weight = recency × importance × utility × confidence × frequency.
  Пакетное обновление через LIMIT+OFFSET (порциями), не всей таблицы.
- Асинхронный буфер записи: накопление в RAM, сброс пакетом раз в 10 минут
  или при достижении порога. Thread-safe. Sync-fallback при переполнении.

Без LLM. Только CPU + диск.
"""

import math
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from utils.utils_logger import get_logger


class EpisodicMemory:
    # --- Параметры ACT-R decay ---
    HALF_LIFE_DAYS = 1.0          # период полураспа recency: за 1 день вес падает вдвое
    DECAY_BATCH_SIZE = 100        # сколько строк обновлять за один проход
    DECAY_INTERVAL_SEC = 3600     # перерасчёт весов — раз в час

    # --- Параметры буфера записи ---
    BUFFER_FLUSH_INTERVAL_SEC = 600   # 10 минут
    BUFFER_FLUSH_THRESHOLD = 50       # сброс при накоплении 50 эпизодов
    BUFFER_HARD_LIMIT = 500           # при превышении — принудительная sync-запись

    def __init__(self, db):
        self.db = db
        self.logger = get_logger("Episodic")

        # RAM-буфер ожидающих записи эпизодов
        self._buffer: deque = deque()
        self._lock = threading.Lock()

        # Управление фоновыми потоками
        self._stop_event = threading.Event()
        self._writer_thread: Optional[threading.Thread] = None
        self._decay_thread: Optional[threading.Thread] = None

    # ==================================================================
    # Публичный API
    # ==================================================================
    def record_episode(self, user_text: str, echo_response: str, importance: float = 0.5) -> None:
        """
        Добавляет эпизод в RAM-буфер. Реальная запись в SQLite — фоновым потоком.
        При переполнении буфера — немедленная sync-запись (защита от потери данных).
        """
        if not user_text and not echo_response:
            return

        importance = max(0.0, min(importance, 1.0))
        episode = (user_text or "", echo_response or "", importance)

        with self._lock:
            self._buffer.append(episode)
            overflow = len(self._buffer) > self.BUFFER_HARD_LIMIT

        if overflow:
            self.logger.warning("Буфер EpisodicMemory переполнен — принудительная sync-запись.")
            self.flush()

    def get_recent_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Возвращает последние эпизоды (по last_accessed DESC).
        При чтении обновляет last_accessed и access_count (ACT-R recency/frequency).
        """
        self.flush()

        rows = self.db.fetchall(
            "SELECT id, user_text, echo_response, importance, weight "
            "FROM episodic_log ORDER BY last_accessed DESC LIMIT ?",
            (limit,)
        )

        result = []
        now_iso = datetime.now().isoformat()
        ids_to_touch = []
        for ep_id, user_text, echo_response, importance, weight in rows:
            result.append({
                "id": ep_id,
                "user_text": user_text,
                "echo_response": echo_response,
                "importance": importance,
                "weight": weight,
            })
            ids_to_touch.append(ep_id)

        if ids_to_touch:
            placeholders = ",".join("?" * len(ids_to_touch))
            self.db.execute(
                f"UPDATE episodic_log SET last_accessed = ?, access_count = access_count + 1 "
                f"WHERE id IN ({placeholders})",
                (now_iso, *ids_to_touch)
            )

        return result

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Полнотекстовый поиск по эпизодам. Использует FTS5 если доступен,
        иначе падает на LIKE-поиск.
        """
        if not query or not query.strip():
            return []
        self.flush()

        if self.db.fts5_available():
            rows = self.db.fetchall(
                "SELECT e.id, e.user_text, e.echo_response, e.importance, e.weight "
                "FROM episodic_fts f JOIN episodic_log e ON e.id = f.rowid "
                "WHERE episodic_fts MATCH ? ORDER BY bm25(episodic_fts) LIMIT ?",
                (query, limit)
            )
        else:
            like = f"%{query}%"
            rows = self.db.fetchall(
                "SELECT id, user_text, echo_response, importance, weight "
                "FROM episodic_log "
                "WHERE user_text LIKE ? OR echo_response LIKE ? "
                "ORDER BY last_accessed DESC LIMIT ?",
                (like, like, limit)
            )

        return [
            {
                "id": r[0], "user_text": r[1], "echo_response": r[2],
                "importance": r[3], "weight": r[4],
            }
            for r in rows
        ]

    def get_all_episodes(self) -> List[Dict[str, Any]]:
        """
        Возвращает все незаконсолидированные эпизоды для фазы сна.
        Каждый эпизод содержит базовые поля и извлечённые concepts.
        """
        self.flush()
        rows = self.db.fetchall(
            "SELECT id, user_text, echo_response, importance "
            "FROM episodic_log WHERE consolidated_to_id IS NULL"
        )
        episodes = []
        for ep_id, user_text, echo_response, importance in rows:
            words = (user_text + " " + echo_response).split()
            concepts = [w.strip(".,!?():;\"'-") for w in words if len(w) > 3]
            episodes.append({
                "id": ep_id,
                "concepts": concepts,
                "action": user_text[:100],
                "target": echo_response[:100],
                "importance": importance,
            })
        return episodes

    def get_unconsolidated(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Эпизоды, ещё не сжатые консолидацией (Этап 6)."""
        rows = self.db.fetchall(
            "SELECT id, user_text, echo_response, importance "
            "FROM episodic_log WHERE consolidated_to_id IS NULL "
            "ORDER BY last_accessed DESC LIMIT ?",
            (limit,)
        )
        return [
            {"id": r[0], "user_text": r[1], "echo_response": r[2], "importance": r[3]}
            for r in rows
        ]

    def mark_consolidated(self, source_id: int, target_id: Optional[int]) -> None:
        """Помечает эпизод как сжатый в consolidated_to_id (Этап 6)."""
        self.db.execute(
            "UPDATE episodic_log SET consolidated_to_id = ? WHERE id = ?",
            (target_id, source_id)
        )

    # ==================================================================
    # Фоновые потоки
    # ==================================================================
    def start(self) -> None:
        """Запускает фоновые потоки: writer (сброс буфера) и decay (перерасчёт весов)."""
        if self._writer_thread and self._writer_thread.is_alive():
            return
        self._stop_event.clear()

        self._writer_thread = threading.Thread(
            target=self._writer_loop, name="EpisodicWriter", daemon=True
        )
        self._decay_thread = threading.Thread(
            target=self._decay_loop, name="EpisodicDecay", daemon=True
        )
        self._writer_thread.start()
        self._decay_thread.start()
        self.logger.info("EpisodicMemory запущена (writer + decay потоки).")

    def stop(self) -> None:
        """Останавливает фоновые потоки и сбрасывает буфер."""
        self._stop_event.set()
        self.flush()
        self.logger.info("EpisodicMemory остановлена.")

    def flush(self) -> int:
        """
        Принудительно сбрасывает накопленный буфер в SQLite пакетом.
        Возвращает количество записанных эпизодов. Thread-safe.
        """
        with self._lock:
            if not self._buffer:
                return 0
            batch = list(self._buffer)
            self._buffer.clear()

        if not batch:
            return 0

        now_iso = datetime.now().isoformat()
        params_seq = [
            (user_text, echo_response, importance, now_iso, importance, now_iso)
            for (user_text, echo_response, importance) in batch
        ]
        try:
            self.db.executemany(
                "INSERT INTO episodic_log "
                "(user_text, echo_response, weight, last_accessed, importance, created) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                params_seq
            )
            self.logger.info(f"EpisodicMemory: записано {len(params_seq)} эпизодов.")
            return len(params_seq)
        except Exception as e:
            with self._lock:
                for item in batch:
                    self._buffer.appendleft(item)
            self.logger.error(f"Ошибка пакетной записи эпизодов: {e}")
            return 0

    # ==================================================================
    # Внутренние циклы потоков
    # ==================================================================
    def _writer_loop(self) -> None:
        """Сброс буфера раз в BUFFER_FLUSH_INTERVAL_SEC или при достижении порога."""
        while not self._stop_event.is_set():
            for _ in range(self.BUFFER_FLUSH_INTERVAL_SEC):
                if self._stop_event.is_set():
                    break
                with self._lock:
                    size = len(self._buffer)
                if size >= self.BUFFER_FLUSH_THRESHOLD:
                    break
                time.sleep(1)
            self.flush()

    def _decay_loop(self) -> None:
        """Перерасчёт ACT-R весов раз в DECAY_INTERVAL_SEC, пакетно."""
        while not self._stop_event.is_set():
            for _ in range(self.DECAY_INTERVAL_SEC):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
            try:
                self._apply_decay_batch()
            except Exception as e:
                self.logger.error(f"Ошибка ACT-R decay: {e}")

    # ==================================================================
    # ACT-R decay
    # ==================================================================
    def _apply_decay_batch(self) -> int:
        """
        Перерасчёт weight = recency × importance × utility × confidence × frequency
        для пачки строк (LIMIT+OFFSET). Возвращает число обновлённых строк.
        """
        now = datetime.now()
        updated_total = 0
        offset = 0

        while not self._stop_event.is_set():
            rows = self.db.fetchall(
                "SELECT id, last_accessed, importance, access_count "
                "FROM episodic_log ORDER BY id LIMIT ? OFFSET ?",
                (self.DECAY_BATCH_SIZE, offset)
            )
            if not rows:
                break

            updates = []
            for ep_id, last_accessed, importance, access_count in rows:
                weight = self._compute_weight(now, last_accessed, importance, access_count)
                updates.append((weight, ep_id))

            if updates:
                self.db.executemany(
                    "UPDATE episodic_log SET weight = ? WHERE id = ?",
                    updates
                )
                updated_total += len(updates)
            offset += self.DECAY_BATCH_SIZE

        if updated_total:
            self.logger.info(f"ACT-R decay: обновлено весов {updated_total}.")
        return updated_total

    def _compute_weight(
        self, now: datetime, last_accessed: Optional[str],
        importance: float, access_count: int
    ) -> float:
        """
        weight = recency × importance × utility × confidence × frequency
        Все множители в [0, 1], итог в [0, 1].
        """
        recency = self._recency_factor(now, last_accessed)
        imp = max(0.0, min(float(importance or 0.5), 1.0))
        freq = 1.0 - math.exp(-0.3 * max(0, int(access_count or 0)))
        utility = 1.0 - math.exp(-0.1 * max(0, int(access_count or 0)))
        confidence = imp
        return max(0.0, min(1.0, recency * imp * utility * confidence * freq))

    def _recency_factor(self, now: datetime, last_accessed: Optional[str]) -> float:
        """Экспоненциальный спад: за HALF_LIFE_DAYS вес падает вдвое."""
        if not last_accessed:
            return 0.1
        try:
            accessed = datetime.fromisoformat(str(last_accessed))
        except (ValueError, TypeError):
            return 0.1

        age_days = max(0.0, (now - accessed).total_seconds() / 86400.0)
        return 0.5 ** (age_days / self.HALF_LIFE_DAYS)


# ==================================================================
# ВСТРОЕННЫЕ ТЕСТЫ
# ==================================================================
if __name__ == "__main__":
    import sqlite3
    import tempfile

    class TestDB:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
            self.lock = threading.Lock()
            self.conn.execute("""CREATE TABLE episodic_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_text TEXT, echo_response TEXT, weight REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0, last_accessed TEXT,
                importance REAL DEFAULT 0.5, consolidated_to_id INTEGER, created TEXT
            )""")
            self._fts5_available = False
            self.conn.commit()

        def execute(self, q, p=()):
            with self.lock:
                cur = self.conn.execute(q, p)
                self.conn.commit()
                return cur

        def executemany(self, q, p):
            with self.lock:
                cur = self.conn.executemany(q, p)
                self.conn.commit()
                return cur

        def fetchone(self, q, p=()):
            with self.lock:
                return self.conn.execute(q, p).fetchone()

        def fetchall(self, q, p=()):
            with self.lock:
                return self.conn.execute(q, p).fetchall()

        def fts5_available(self):
            return self._fts5_available

    db = TestDB()
    mem = EpisodicMemory(db)

    mem.record_episode("Привет", "Здравствуй.", importance=0.6)
    mem.record_episode("Расскажи о себе", "Я Эхо.", importance=0.9)
    written = mem.flush()
    assert written == 2, f"Ожидалось 2 эпизода, записано {written}"
    print(f"[OK] Тест 1 (запись+flush): {written} эпизода")

    ctx = mem.get_recent_context(limit=5)
    assert len(ctx) == 2
    cnt = db.fetchone("SELECT access_count FROM episodic_log WHERE user_text = 'Привет'")[0]
    assert cnt == 1
    print(f"[OK] Тест 2 (get_recent_context): access_count = {cnt}")

    mem._apply_decay_batch()
    w = db.fetchone("SELECT weight FROM episodic_log WHERE user_text = 'Привет'")[0]
    assert 0.0 <= w <= 1.0
    print(f"[OK] Тест 3 (ACT-R decay): weight = {w:.4f}")

    found = mem.search("себе")
    assert len(found) == 1
    print(f"[OK] Тест 4 (search LIKE): найдено {len(found)}")

    mem.mark_consolidated(1, 99)
    cons = db.fetchone("SELECT consolidated_to_id FROM episodic_log WHERE id = 1")[0]
    assert cons == 99
    print("[OK] Тест 5 (mark_consolidated)")

    all_eps = mem.get_all_episodes()
    print(f"[OK] Тест 6 (get_all_episodes): получено {len(all_eps)} эпизодов")

    print("\n[OK] Все тесты EpisodicMemory v1.0 пройдены.")