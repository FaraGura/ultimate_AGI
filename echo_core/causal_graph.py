"""Expanded causal graph for Echo v16.1 — stdlib only, no networkx."""

import json
import os
import re
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from utils.utils_logger import get_logger

EDGE_TYPES = frozenset({
    "causal", "correlation", "hypothesis", "personal_experience", "enables",
})


def normalize(text: str) -> str:
    """Каноническая форма: нижний регистр, без дефисов, но с сохранением пробелов."""
    if not text:
        return ""
    return text.strip().lower().replace("-", "")


class CausalGraph:
    def __init__(self, db):
        self.db = db
        self.logger = get_logger("CausalGraph")
        self.axiom_concepts: Set[str] = set()
        self._ensure_tables()

    def _ensure_tables(self):
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS anchor_nodes (
                concept_name TEXT PRIMARY KEY,
                reason TEXT NOT NULL DEFAULT 'core axiom',
                provenance TEXT DEFAULT 'tabula_rasa_core'
            )"""
        )
        try:
            self.db.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique
                   ON causal_edges(source_concept, target_concept, relation_type)"""
            )
        except Exception:
            pass

    def add_node(self, node_id: str, name: str = None):
        """Добавляет узел-концепт в граф (для команды научи:)."""
        node_norm = normalize(node_id)
        self.db.execute(
            "INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, provenance_source, lamport_tick, physical_time) "
            "VALUES (?, 'concept', '{}', 'user_teaching', 0, 0)",
            (node_norm,)
        )

    def add_edge(self, source: str, target: str, relation: str, confidence: float = 0.5):
        source_norm = normalize(source)
        target_norm = normalize(target)
        relation = relation or "causal"
        confidence = max(0.0, min(1.0, float(confidence)))
        self.db.execute(
            """INSERT OR REPLACE INTO causal_edges
               (source_concept, target_concept, relation_type, confidence,
                evidence_count, last_updated)
               VALUES (?, ?, ?, ?,
                COALESCE((SELECT evidence_count + 1 FROM causal_edges
                          WHERE source_concept = ? AND target_concept = ?
                          AND relation_type = ?), 1), ?)""",
            (
                source_norm, target_norm, relation, confidence,
                source_norm, target_norm, relation, str(datetime.now()),
            ),
        )

    def update_confidence(self, source: str, target: str, relation: str, delta: float):
        source_norm = normalize(source)
        target_norm = normalize(target)
        row = self.db.fetchone(
            """SELECT confidence FROM causal_edges
               WHERE source_concept = ? AND target_concept = ? AND relation_type = ?""",
            (source_norm, target_norm, relation),
        )
        if row:
            new_conf = max(0.0, min(1.0, row[0] + delta))
            self.db.execute(
                """UPDATE causal_edges SET confidence = ?, last_updated = ?
                   WHERE source_concept = ? AND target_concept = ? AND relation_type = ?""",
                (new_conf, str(datetime.now()), source_norm, target_norm, relation),
            )

    def add_anchor_node(self, concept_name: str, reason: str = "core axiom"):
        concept_norm = normalize(concept_name)
        self.db.execute(
            """INSERT OR REPLACE INTO anchor_nodes (concept_name, reason, provenance)
               VALUES (?, ?, 'tabula_rasa_core')""",
            (concept_norm, reason),
        )
        self.axiom_concepts.add(concept_norm)

    def is_anchor_node(self, concept_name: str) -> bool:
        concept_norm = normalize(concept_name)
        if concept_norm in self.axiom_concepts:
            return True
        row = self.db.fetchone(
            "SELECT 1 FROM anchor_nodes WHERE concept_name = ?", (concept_norm,)
        )
        return row is not None

    def add_axiom(self, concept: str):
        self.add_anchor_node(concept)

    def is_axiom(self, concept: str) -> bool:
        return self.is_anchor_node(concept)

    def get_edges(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> List[Dict]:
        query = (
            "SELECT source_concept, target_concept, relation_type, confidence, evidence_count "
            "FROM causal_edges WHERE 1=1"
        )
        params: list = []
        if source:
            query += " AND source_concept = ?"
            params.append(normalize(source))
        if target:
            query += " AND target_concept = ?"
            params.append(normalize(target))
        if relation:
            query += " AND relation_type = ?"
            params.append(relation)
        rows = self.db.fetchall(query, tuple(params))
        return [
            {
                "source": r[0],
                "target": r[1],
                "relation": r[2],
                "confidence": r[3],
                "evidence_count": r[4],
            }
            for r in rows
        ]

    def get_causes(self, event: str) -> List[Dict]:
        event_norm = normalize(event)
        rows = self.db.fetchall(
            """SELECT source_concept, relation_type, confidence
               FROM causal_edges WHERE target_concept = ?
               ORDER BY confidence DESC""",
            (event_norm,),
        )
        return [
            {"cause": r[0], "relation": r[1], "confidence": r[2]}
            for r in rows
        ]

    def get_consequences(self, action: str) -> List[Dict]:
        action_norm = normalize(action)
        rows = self.db.fetchall(
            """SELECT target_concept, relation_type, confidence
               FROM causal_edges WHERE source_concept = ?
               ORDER BY confidence DESC""",
            (action_norm,),
        )
        return [
            {"consequence": r[0], "relation": r[1], "confidence": r[2]}
            for r in rows
        ]

    def find_facts_about(self, concept: str, min_confidence: float = 0.3) -> List[Dict]:
        norm = normalize(concept)
        rows = self.db.fetchall(
            """SELECT source_concept, target_concept, relation_type, confidence
               FROM causal_edges
               WHERE confidence >= ?
                 AND (source_concept = ? OR target_concept = ?)""",
            (min_confidence, norm, norm),
        )
        return [
            {
                "source": r[0],
                "target": r[1],
                "relation": r[2],
                "confidence": r[3],
            }
            for r in rows
        ]

    def edge_count(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) FROM causal_edges")
        return row[0] if row else 0

    def _adjacency(self, min_confidence: float = 0.0) -> Dict[str, List[str]]:
        rows = self.db.fetchall(
            """SELECT source_concept, target_concept FROM causal_edges
               WHERE confidence >= ?""",
            (min_confidence,),
        )
        adj: Dict[str, List[str]] = {}
        for src, tgt in rows:
            adj.setdefault(src, []).append(tgt)
        return adj

    def has_path(self, start: str, end: str, min_confidence: float = 0.0) -> bool:
        start_norm = normalize(start)
        end_norm = normalize(end)
        if start_norm == end_norm:
            return True
        adj = self._adjacency(min_confidence)
        if start_norm not in adj:
            return False
        visited = {start_norm}
        queue = deque([start_norm])
        while queue:
            node = queue.popleft()
            for nxt in adj.get(node, []):
                if nxt == end_norm:
                    return True
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    def validate_path(self, source: str, target: str, min_confidence: float = 0.5) -> bool:
        return self.has_path(source, target, min_confidence)

    def get_subgraph(self, concept: str, depth: int = 2, min_confidence: float = 0.3):
        concept_norm = normalize(concept)
        rows = self.db.fetchall(
            """SELECT source_concept, target_concept, relation_type, confidence
               FROM causal_edges WHERE confidence >= ?""",
            (min_confidence,),
        )
        adj: Dict[str, List[Tuple[str, dict]]] = {}
        for src, tgt, rel, conf in rows:
            adj.setdefault(src, []).append((tgt, {"relation": rel, "confidence": conf}))
            adj.setdefault(tgt, [])

        if concept_norm not in adj:
            return []

        nodes = {concept_norm}
        for _ in range(depth):
            frontier = set()
            for n in nodes:
                for tgt, _ in adj.get(n, []):
                    frontier.add(tgt)
                for src, targets in adj.items():
                    if any(t == n for t, _ in targets):
                        frontier.add(src)
            nodes.update(frontier)

        result = []
        for src, targets in adj.items():
            if src not in nodes:
                continue
            for tgt, data in targets:
                if tgt in nodes:
                    result.append((src, tgt, data))
        return result

    def pruning(self, min_confidence: float = 0.2, min_age_days: int = 7):
        cutoff = datetime.fromtimestamp(
            datetime.now().timestamp() - min_age_days * 86400
        ).isoformat()
        self.db.execute(
            """DELETE FROM causal_edges
               WHERE confidence < ? AND last_updated < ?
               AND source_concept NOT IN (SELECT concept_name FROM anchor_nodes)
               AND target_concept NOT IN (SELECT concept_name FROM anchor_nodes)""",
            (min_confidence, cutoff),
        )
        self.logger.info("Causal graph pruning complete.")

    def export_to_json(self, filepath: str) -> str:
        edges = self.get_edges()
        nodes_set: Set[str] = set()
        links = []
        for edge in edges:
            nodes_set.add(edge["source"])
            nodes_set.add(edge["target"])
            links.append({
                "source": edge["source"],
                "target": edge["target"],
                "type": edge["relation"],
                "probability": edge["confidence"],
            })
        nodes = [
            {"id": n, "is_anchor": self.is_anchor_node(n)}
            for n in sorted(nodes_set)
        ]
        payload = {"nodes": nodes, "links": links}
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.logger.info("Exported causal graph to %s", abs_path)
        return abs_path