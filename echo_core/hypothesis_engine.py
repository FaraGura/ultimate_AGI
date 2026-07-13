"""Hypothesis engine — groups observations by concept_a + relation_type."""

from datetime import datetime
from typing import Dict, List, Optional


class HypothesisEngine:
    HYPOTHESIS_THRESHOLD = 3
    RULE_THRESHOLD = 10

    def __init__(self, db, causal_graph):
        self.db = db
        self.causal_graph = causal_graph
        self._create_tables()

    def _create_tables(self):
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_a TEXT NOT NULL,
                concept_b TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                timestamp REAL,
                context TEXT
            )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS hypotheses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_a TEXT NOT NULL,
                concept_b TEXT,
                relation_type TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                evidence_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at REAL,
                last_updated REAL,
                rejection_reason TEXT,
                UNIQUE(concept_a, relation_type)
            )"""
        )

    def add_observation(
        self,
        concept_a: str,
        concept_b: str,
        relation_type: str = "enables",
        context: str = "",
    ):
        now = datetime.now().timestamp()
        self.db.execute(
            """INSERT INTO observations
               (concept_a, concept_b, relation_type, timestamp, context)
               VALUES (?, ?, ?, ?, ?)""",
            (concept_a, concept_b, relation_type, now, context),
        )
        self._update_hypothesis(concept_a, relation_type)

    def _count_observations(self, concept_a: str, relation_type: str) -> int:
        row = self.db.fetchone(
            """SELECT COUNT(*) FROM observations
               WHERE concept_a = ? AND relation_type = ?""",
            (concept_a, relation_type),
        )
        return row[0] if row else 0

    def _latest_concept_b(self, concept_a: str, relation_type: str) -> str:
        row = self.db.fetchone(
            """SELECT concept_b FROM observations
               WHERE concept_a = ? AND relation_type = ?
               ORDER BY id DESC LIMIT 1""",
            (concept_a, relation_type),
        )
        return row[0] if row else "unknown"

    def _update_hypothesis(self, concept_a: str, relation_type: str):
        count = self._count_observations(concept_a, relation_type)
        if count < self.HYPOTHESIS_THRESHOLD:
            return

        confidence = min(count / 10.0, 1.0)
        status = "rule" if count >= self.RULE_THRESHOLD else "pending"
        if status == "rule":
            confidence = 1.0

        concept_b = self._latest_concept_b(concept_a, relation_type)
        now = datetime.now().timestamp()

        existing = self.db.fetchone(
            """SELECT id, status FROM hypotheses
               WHERE concept_a = ? AND relation_type = ?""",
            (concept_a, relation_type),
        )

        if existing:
            hyp_id, old_status = existing
            if old_status == "rejected":
                return
            self.db.execute(
                """UPDATE hypotheses
                   SET concept_b = ?, confidence = ?, evidence_count = ?,
                       status = ?, last_updated = ?
                   WHERE id = ?""",
                (concept_b, confidence, count, status, now, hyp_id),
            )
        else:
            self.db.execute(
                """INSERT INTO hypotheses
                   (concept_a, concept_b, relation_type, confidence, evidence_count,
                    status, created_at, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    concept_a, concept_b, relation_type, confidence, count,
                    status, now, now,
                ),
            )

        edge_type = "causal" if status == "rule" else "hypothesis"
        self.causal_graph.add_edge(concept_a, concept_b, edge_type, confidence)

    def get_hypotheses(self, status: Optional[str] = None) -> List[Dict]:
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM hypotheses WHERE status = ? ORDER BY id",
                (status,),
            )
        else:
            rows = self.db.fetchall("SELECT * FROM hypotheses ORDER BY id")

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "concept_a": row[1],
                "concept_b": row[2],
                "relation_type": row[3],
                "confidence": row[4],
                "evidence_count": row[5],
                "status": row[6],
                "created_at": row[7],
                "last_updated": row[8],
                "rejection_reason": row[9],
            })
        return results