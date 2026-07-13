# echo_core/merge_engine.py
"""
Merge Engine v1.0 — детерминированное слияние графов.
Используется при объединении веток Альтеров.
Конвейер: HLC Drift → Canonicalization → Stage A → Stage B → Unified Core.
"""

import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MergeResult:
    nodes_added: int = 0
    edges_added: int = 0
    conflicts_detected: int = 0
    unresolved: list = field(default_factory=list)


class MergeEngine:
    """Контролируемое слияние графов от разных Альтеров."""

    def __init__(self, db, canonicalize_fn=None):
        self.db = db
        self.canonicalize = canonicalize_fn or self._default_cid

    def _default_cid(self, node_type: str, payload: str) -> str:
        raw = f"{node_type}:{payload}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def merge_graphs(self, source_alter_id: str, target_context_flags: int = 1) -> MergeResult:
        """
        Переносит узлы и рёбра из графа source_alter_id в GLOBAL (или указанный контекст).
        Дубликаты (по CID) пропускаются. Конфликты фиксируются.
        """
        result = MergeResult()

        # 1. Перенос узлов
        source_nodes = self.db.fetchall(
            """SELECT node_id, node_type, payload, provenance_source, lamport_tick
               FROM graph_nodes
               WHERE provenance_source = ? OR origin_instance_id = ?""",
            (source_alter_id, source_alter_id)
        )

        for row in source_nodes:
            node_id, node_type, payload, provenance, tick = row
            cid = self.canonicalize(node_type, payload or "{}")

            # Проверяем, нет ли уже узла с таким CID в целевом контексте
            existing = self.db.fetchone(
                "SELECT node_id FROM graph_nodes WHERE semantic_signature = ? AND (context_flags & ?) != 0",
                (cid, target_context_flags)
            )
            if existing:
                result.conflicts_detected += 1
                result.unresolved.append({
                    "type": "duplicate_node",
                    "source": source_alter_id,
                    "node_id": node_id,
                    "existing_id": existing[0]
                })
                continue

            # Добавляем узел в целевой контекст
            self.db.execute(
                """INSERT OR IGNORE INTO graph_nodes
                   (node_id, node_type, payload, context_flags, provenance_source, lamport_tick)
                   VALUES (?, ?, ?, ?, 'merged', ?)""",
                (f"{source_alter_id}_{node_id}", node_type, payload, target_context_flags, tick)
            )
            result.nodes_added += 1

        # 2. Перенос рёбер
        source_edges = self.db.fetchall(
            """SELECT source_node_id, target_node_id, relation_type, confidence_score, lamport_tick
               FROM graph_edges
               WHERE provenance_source = ? OR origin_instance_id = ?""",
            (source_alter_id, source_alter_id)
        )

        for row in source_edges:
            src, tgt, rel, conf, tick = row
            # Проверяем, существует ли уже такое ребро
            existing_edge = self.db.fetchone(
                """SELECT edge_id FROM graph_edges
                   WHERE source_node_id = ? AND target_node_id = ? AND relation_type = ?""",
                (f"{source_alter_id}_{src}", f"{source_alter_id}_{tgt}", rel)
            )
            if existing_edge:
                continue

            self.db.execute(
                """INSERT INTO graph_edges
                   (edge_id, source_node_id, target_node_id, relation_type,
                    context_flags, provenance_source, confidence_score, lamport_tick)
                   VALUES (?, ?, ?, ?, ?, 'merged', ?, ?)""",
                (f"merge_{source_alter_id}_{src}_{tgt}",
                 f"{source_alter_id}_{src}",
                 f"{source_alter_id}_{tgt}",
                 rel, target_context_flags, conf, tick)
            )
            result.edges_added += 1

        return result


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock

    mock_db = Mock()
    mock_db.fetchall.return_value = []
    mock_db.fetchone.return_value = None

    engine = MergeEngine(mock_db)

    result = engine.merge_graphs("echo_test")
    assert result.nodes_added == 0
    assert result.edges_added == 0
    print("✅ MergeEngine тест пройден (пустой граф)")

    mock_db.fetchall.side_effect = [
        [("n1", "concept", '{"val":"x"}', "echo_test", 1)],
        [("n1", "n2", "causes", 0.8, 1)]
    ]
    mock_db.fetchone.return_value = None
    result = engine.merge_graphs("echo_test")
    assert result.nodes_added == 1
    assert result.edges_added == 1
    print(f"✅ MergeEngine тест пройден (узлов: {result.nodes_added}, рёбер: {result.edges_added})")

    print("\n🔥 Все тесты MergeEngine пройдены.")