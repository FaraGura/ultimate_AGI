# memory/memory_interface.py
"""
Memory API v1.0 — минимальные интерфейсы для разных типов памяти.
Обёртки над DatabaseManager. Не заменяют его, а дают явные точки входа.
"""


class KnowledgeMemory:
    """Факты, законы, закристаллизованные знания (survival_matrix, learned_knowledge)."""

    def __init__(self, db):
        self.db = db

    def save_law(self, context: str, essence: str, blind_spots: str,
                 wisdom: str, confidence: float = 1.0, tags: str = "[]"):
        self.db.execute(
            """INSERT OR REPLACE INTO survival_matrix
               (context, core_essence, blind_spots, actionable_wisdom,
                confidence_score, failure_exceptions, tags, reflex_level, created)
               VALUES (?, ?, ?, ?, ?, '[]', ?, 0, datetime('now'))""",
            (context, essence, blind_spots, wisdom, confidence, tags)
        )

    def save_fact(self, content: str, knowledge_type: str = "fact",
                  category: str = None, weight: float = 1.0):
        self.db.execute(
            """INSERT OR REPLACE INTO learned_knowledge
               (knowledge_type, category, content, weight, uses, created)
               VALUES (?, ?, ?, ?, 0, datetime('now'))""",
            (knowledge_type, category, content, weight)
        )

    def search_laws(self, keyword: str, limit: int = 5):
        return self.db.fetchall(
            """SELECT id, context, core_essence, actionable_wisdom, confidence_score
               FROM survival_matrix
               WHERE context LIKE ? OR core_essence LIKE ? OR actionable_wisdom LIKE ?
               ORDER BY confidence_score DESC LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)
        )

    def search_facts(self, keyword: str, limit: int = 5):
        return self.db.fetchall(
            """SELECT id, content, knowledge_type, weight
               FROM learned_knowledge
               WHERE content LIKE ?
               ORDER BY weight DESC LIMIT ?""",
            (f"%{keyword}%", limit)
        )


class ExperienceMemory:
    """Опыт, ошибки, решения, события (memory, reflection_log)."""

    def __init__(self, db):
        self.db = db

    def save_experience(self, user_text: str, answer: str, weight: float = 1.0):
        self.db.execute(
            """INSERT INTO memory (user_text, answer, weight, uses, created)
               VALUES (?, ?, ?, 0, datetime('now'))""",
            (user_text, answer, weight)
        )

    def log_reflection(self, event_type: str, summary: str, details: str = ""):
        self.db.execute(
            """INSERT INTO reflection_log (timestamp, event_type, summary, details)
               VALUES (datetime('now'), ?, ?, ?)""",
            (event_type, summary, details)
        )

    def get_recent_experiences(self, limit: int = 10):
        return self.db.fetchall(
            "SELECT user_text, answer, weight FROM memory ORDER BY id DESC LIMIT ?",
            (limit,)
        )


class StateMemory:
    """Состояние агента, конфигурация, снапшоты (SelfState, assistant_config)."""

    def __init__(self, db):
        self.db = db

    def save_state_snapshot(self, state_json: str):
        self.db.execute(
            """INSERT INTO reflection_log (timestamp, event_type, summary, details)
               VALUES (datetime('now'), 'state_snapshot', ?, '')""",
            (state_json,)
        )

    def get_last_snapshot(self):
        return self.db.fetchone(
            "SELECT summary FROM reflection_log WHERE event_type='state_snapshot' ORDER BY id DESC LIMIT 1"
        )


class GraphMemory:
    """Узлы и рёбра CausalGraph (graph_nodes, graph_edges, concept_nodes, causal_edges)."""

    def __init__(self, db):
        self.db = db

    def add_node(self, node_id: str, node_type: str, payload: dict = None,
                 context_flags: int = 1, provenance: str = "tabula_rasa",
                 lamport_tick: int = 0, created_by: str = ""):
        import json
        payload_blob = json.dumps(payload or {})
        self.db.execute(
            """INSERT OR REPLACE INTO graph_nodes
               (node_id, node_type, payload, context_flags, provenance_source,
                lamport_tick, physical_time, created_by_module)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
            (node_id, node_type, payload_blob, context_flags, provenance,
             lamport_tick, created_by)
        )

    def add_edge(self, source: str, target: str, relation: str,
                 context_flags: int = 1, provenance: str = "tabula_rasa",
                 confidence: float = 0.7, lamport_tick: int = 0,
                 created_by: str = ""):
        import uuid
        edge_id = str(uuid.uuid4())
        self.db.execute(
            """INSERT OR REPLACE INTO graph_edges
               (edge_id, source_node_id, target_node_id, relation_type,
                context_flags, provenance_source, confidence_score,
                lamport_tick, created_by_module)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (edge_id, source, target, relation, context_flags, provenance,
             confidence, lamport_tick, created_by)
        )

    def get_subgraph(self, node_id: str, depth: int = 1, context_flags: int = 1):
        """Возвращает рёбра, связанные с узлом, с фильтром по контексту."""
        return self.db.fetchall(
            """SELECT source_node_id, target_node_id, relation_type, confidence_score
               FROM graph_edges
               WHERE (source_node_id = ? OR target_node_id = ?)
                 AND (context_flags & ?) != 0""",
            (node_id, node_id, context_flags)
        )

    def find_nodes_by_type(self, node_type: str, limit: int = 100):
        return self.db.fetchall(
            "SELECT node_id, payload FROM graph_nodes WHERE node_type = ? LIMIT ?",
            (node_type, limit)
        )


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from memory_db import DatabaseManager
    db = DatabaseManager()

    gm = GraphMemory(db)
    gm.add_node("test_node", "symbol", {"value": "тест"})
    gm.add_edge("test_node", "test_node", "self_ref", created_by="test")

    nodes = gm.find_nodes_by_type("symbol")
    assert len(nodes) > 0
    print("✅ GraphMemory тест пройден")

    km = KnowledgeMemory(db)
    km.save_law("тест", "суть", "зоны", "мудрость")
    laws = km.search_laws("тест")
    assert len(laws) > 0
    print("✅ KnowledgeMemory тест пройден")

    em = ExperienceMemory(db)
    em.save_experience("привет", "здравствуй")
    exps = em.get_recent_experiences(1)
    assert len(exps) > 0
    print("✅ ExperienceMemory тест пройден")

    print("\n🔥 Все тесты Memory API пройдены.")