# echo_core/conceptual_core/concept_library.py
"""
ConceptLibrary — хранилище и поиск концептов.
Часть реструктурированного ConceptualCore.
Отвечает только за хранение: свойства, аффордансы, ограничения, связи.
Не зависит от KnowledgeExtractor и CausalGraph.
"""
from typing import Dict, List, Optional, Any
from echo_core.core_types.concept import Concept


class ConceptLibrary:
    """
    Хранилище концептов Echo.
    Быстрый доступ к свойствам, аффордансам и ограничениям объектов.
    """
    def __init__(self, db):
        self.db = db
        self._cache: Dict[str, Concept] = {}
        self._load_from_db()

    def _load_from_db(self):
        """Загружает концепты из graph_nodes в кэш."""
        rows = self.db.fetchall(
            "SELECT node_id, payload FROM graph_nodes WHERE node_type = 'concept'"
        )
        import json
        for node_id, payload_blob in rows:
            try:
                payload = json.loads(payload_blob) if isinstance(payload_blob, str) else {}
                concept = Concept(
                    id=node_id,
                    name=payload.get("value", node_id),
                    concept_type=payload.get("concept_type", "object"),
                    properties=payload.get("properties", {}),
                    affordances=payload.get("affordances", []),
                    constraints=payload.get("constraints", []),
                    source=payload.get("source", "unknown"),
                    confidence=payload.get("confidence", 0.5)
                )
                self._cache[node_id] = concept
            except Exception:
                pass

    def get(self, concept_id: str) -> Optional[Concept]:
        """Возвращает концепт по ID или None."""
        return self._cache.get(concept_id)

    def find_by_name(self, name: str) -> Optional[Concept]:
        """Ищет концепт по имени (точное совпадение)."""
        name_lower = name.lower().strip()
        for concept in self._cache.values():
            if concept.name.lower() == name_lower:
                return concept
        return None

    def search(self, query: str, limit: int = 5) -> List[Concept]:
        """Ищет концепты по части имени."""
        query_lower = query.lower().strip()
        results = []
        for concept in self._cache.values():
            if query_lower in concept.name.lower():
                results.append(concept)
                if len(results) >= limit:
                    break
        return results

    def add_concept(self, concept: Concept) -> bool:
        """Добавляет новый концепт в память и БД."""
        import json
        try:
            payload = {
                "value": concept.name,
                "concept_type": concept.concept_type,
                "properties": concept.properties,
                "affordances": concept.affordances,
                "constraints": concept.constraints,
                "source": concept.source,
                "confidence": concept.confidence
            }
            self.db.execute(
                """INSERT OR REPLACE INTO graph_nodes
                   (node_id, node_type, payload, provenance_source, lamport_tick, physical_time)
                   VALUES (?, 'concept', ?, 'concept_library', 0, 0)""",
                (concept.id, json.dumps(payload, ensure_ascii=False))
            )
            self._cache[concept.id] = concept
            return True
        except Exception:
            return False

    def add_property(self, concept_id: str, prop_name: str, prop_value: Any) -> bool:
        """Добавляет свойство концепту."""
        concept = self._cache.get(concept_id)
        if not concept:
            return False
        concept.properties[prop_name] = prop_value
        return self.add_concept(concept)

    def add_affordance(self, concept_id: str, affordance: str) -> bool:
        """Добавляет аффорданс концепту."""
        concept = self._cache.get(concept_id)
        if not concept:
            return False
        if affordance not in concept.affordances:
            concept.affordances.append(affordance)
        return self.add_concept(concept)

    def has_property(self, concept_id: str, prop_name: str) -> bool:
        """Проверяет наличие свойства у концепта."""
        concept = self._cache.get(concept_id)
        return concept is not None and prop_name in concept.properties

    def can_do(self, concept_id: str, action: str) -> bool:
        """Проверяет, может ли концепт выполнить действие."""
        concept = self._cache.get(concept_id)
        return concept is not None and action in concept.affordances

    def get_all_concepts(self) -> List[Concept]:
        """Возвращает все загруженные концепты."""
        return list(self._cache.values())

    def concept_count(self) -> int:
        """Количество концептов в памяти."""
        return len(self._cache)