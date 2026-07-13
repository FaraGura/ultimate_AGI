# echo_core/memory_manager.py
"""
Memory Manager v1.1 — единый диспетчер памяти Echo.
Добавлен автоматический запуск консолидации при накоплении эпизодов.
"""
import threading
from typing import Optional, List, Dict, Any
from utils.utils_logger import get_logger


class MemoryManager:
    def __init__(self, db, causal_graph, episodic_memory, knowledge_extractor,
                 hypothesis_engine, consolidation_engine, belief_manager):
        self.logger = get_logger("MemoryManager")
        self.db = db
        self.causal = causal_graph
        self.episodic = episodic_memory
        self.knowledge_extractor = knowledge_extractor
        self.hypothesis_engine = hypothesis_engine
        self.consolidation_engine = consolidation_engine
        self.belief_manager = belief_manager

        # Счётчик эпизодов для автоматической консолидации
        self._episode_counter = 0
        self._consolidation_threshold = 20  # запускать консолидацию каждые 20 эпизодов
        self._consolidation_lock = threading.Lock()

        self.logger.info("Memory Manager v1.1 инициализирован")

    def query(self, concept: str, query_type: str = "any") -> Optional[Dict[str, Any]]:
        """Единая точка поиска по всем хранилищам."""
        # 1. Поиск фактов в графе
        if query_type in ("fact", "any"):
            facts = self.causal.find_facts_about(concept)
            if facts:
                return {"source": "causal_graph", "facts": facts}

        # 2. Поиск определений в graph_nodes
        if query_type in ("definition", "any"):
            rows = self.db.fetchall(
                "SELECT payload FROM graph_nodes WHERE node_type = 'concept' AND LOWER(node_id) = ?",
                (concept.lower(),)
            )
            if rows:
                import json
                for row in rows:
                    try:
                        payload = json.loads(row[0]) if isinstance(row[0], str) else {}
                        definition = payload.get("definition")
                        if definition:
                            return {"source": "graph_nodes", "definition": definition}
                    except Exception:
                        pass

        # 3. Поиск эпизодов
        if query_type in ("episode", "any"):
            episodes = self.episodic.search(concept, limit=3)
            if episodes:
                return {"source": "episodic_memory", "episodes": episodes}

        return None

    def remember_fact(self, subject: str, relation: str, obj: str, confidence: float = 0.6) -> bool:
        """Сохраняет факт в граф."""
        try:
            self.causal.add_edge(subject, obj, relation, confidence=confidence)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения факта: {e}")
            return False

    def remember_episode(self, user_text: str, echo_response: str, importance: float = 0.5) -> None:
        """Сохраняет эпизод диалога и запускает консолидацию при накоплении."""
        self.episodic.record_episode(user_text, echo_response, importance=importance)
        self._episode_counter += 1

        # Автоматическая консолидация при накоплении порога
        if self._episode_counter >= self._consolidation_threshold:
            self._try_consolidate()

    def consolidate(self) -> int:
        """Запускает консолидацию эпизодов в знания."""
        unconsolidated = self.episodic.get_unconsolidated(limit=50)
        if not unconsolidated:
            return 0
        count = self.consolidation_engine.run(unconsolidated)
        self.logger.info(f"Консолидация: {count} кластеров")
        return count

    def _try_consolidate(self) -> None:
        """Пытается запустить консолидацию в отдельном потоке."""
        if self._consolidation_lock.acquire(blocking=False):
            try:
                thread = threading.Thread(target=self._run_consolidation, daemon=True)
                thread.start()
            finally:
                self._consolidation_lock.release()

    def _run_consolidation(self) -> None:
        """Фоновый запуск консолидации."""
        try:
            count = self.consolidate()
            if count > 0:
                self._episode_counter = 0
        except Exception as e:
            self.logger.error(f"Ошибка консолидации: {e}")