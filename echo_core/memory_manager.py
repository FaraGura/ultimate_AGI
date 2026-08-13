# echo_core/memory_manager.py
"""
Memory Manager v1.1 — единый диспетчер памяти Echo.
Добавлен автоматический запуск консолидации при накоплении эпизодов.
"""
import threading
from typing import Optional, List, Dict, Any
from utils.utils_logger import get_logger
from echo_core.causal_graph import normalize


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
            facts = self._query_facts(concept)
            if facts:
                return {"source": "knowledge_graph", "facts": facts}

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

    def _query_facts(self, concept: str, limit: int = 80) -> List[Dict[str, Any]]:
        """
        Ищет факты во всех графовых источниках.

        Graph A (`causal_edges`) содержит локальные причинные и обученные связи.
        Graph B (`graph_edges`) содержит импортированные внешние факты
        ConceptNet/Wikidata и выводы BeliefManager. Диалоговый слой не должен
        знать, в какой именно таблице лежит факт, поэтому нормализуем оба
        источника к одному формату.
        """
        concept_norm = normalize(concept)
        if not concept_norm:
            return []

        facts: List[Dict[str, Any]] = []
        seen = set()

        def add_fact(fact: Dict[str, Any]) -> None:
            source = normalize(str(fact.get("source", "")))
            target = normalize(str(fact.get("target", "")))
            relation = str(fact.get("relation", "") or "RELATED_TO").upper()
            if not source or not target:
                return
            key = (source, target, relation, fact.get("store", ""))
            if key in seen:
                return
            seen.add(key)
            fact["source"] = source
            fact["target"] = target
            fact["relation"] = relation
            facts.append(fact)

        for fact in self.causal.find_facts_about(concept_norm) or []:
            add_fact({
                "source": fact.get("source", ""),
                "target": fact.get("target", ""),
                "relation": fact.get("relation", ""),
                "confidence": fact.get("confidence", 0.5),
                "provenance": "causal_edges",
                "store": "causal_edges",
            })

        for fact in self._query_belief_graph(concept_norm, limit=limit):
            add_fact(fact)

        relation_priority = {
            "IS_A": 0,
            "HAS_DEFINITION": 1,
            "HAS_PROPERTY": 2,
            "CAN_DO": 3,
            "CAUSES": 4,
            "LOCATED_IN": 5,
            "RELATED_TO": 6,
        }

        def score(fact: Dict[str, Any]):
            source = fact.get("source", "")
            target = fact.get("target", "")
            relation = fact.get("relation", "")
            exact_source = source == concept_norm
            exact_target = target == concept_norm
            external = "external_db" in str(fact.get("provenance", ""))
            confidence = float(fact.get("confidence", 0.0) or 0.0)
            return (
                0 if exact_source else 1 if exact_target else 2,
                relation_priority.get(relation, 9),
                0 if external else 1,
                -confidence,
                len(target),
            )

        facts.sort(key=score)
        return facts[:limit]

    def _query_belief_graph(self, concept: str, limit: int = 80) -> List[Dict[str, Any]]:
        """Возвращает факты из Graph B (`graph_edges`) в общем формате."""
        rows = self.db.fetchall(
            """SELECT source_node_id, target_node_id, relation_type,
                      confidence_score, provenance_source, provenance, status
               FROM graph_edges
               WHERE (source_node_id = ? OR target_node_id = ?)
                 AND (status IS NULL OR status NOT IN ('rejected', 'outdated', 'superseded'))
               ORDER BY
                 CASE WHEN source_node_id = ? THEN 0 ELSE 1 END,
                 CASE UPPER(relation_type)
                   WHEN 'IS_A' THEN 0
                   WHEN 'HAS_DEFINITION' THEN 1
                   WHEN 'HAS_PROPERTY' THEN 2
                   WHEN 'CAN_DO' THEN 3
                   WHEN 'CAUSES' THEN 4
                   WHEN 'LOCATED_IN' THEN 5
                   ELSE 6
                 END,
                 confidence_score DESC
               LIMIT ?""",
            (concept, concept, concept, limit),
        )
        result: List[Dict[str, Any]] = []
        for source, target, relation, confidence, prov_source, provenance, status in rows:
            result.append({
                "source": source,
                "target": target,
                "relation": relation,
                "confidence": confidence,
                "provenance": provenance or prov_source or "",
                "status": status,
                "store": "graph_edges",
            })
        return result

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
