# echo_core/belief_manager.py

v1.6: receive() получил необязательный параметр fast_path (по умолчанию False).
Если True, Guardian.stage_a_filter вызывается с fast_path=True, пропуская
тяжёлые проверки (_contradiction_check). Это используется FastImporter
для массовой загрузки доверенных источников (Wikidata, ConceptNet).
"""
import json
import copy
from typing import Optional, Union
from sqlite3 import OperationalError
from echo_core.belief import Belief
from echo_core.conflict import Conflict
from echo_core.guardian import Guardian


class BeliefManager:
    def __init__(self, db, guardian=None):
        self.db = db
        self.guardian = guardian or Guardian(db)

    def receive(self, candidate: Union[dict, Belief],
                return_details: bool = False,
                fast_path: bool = False):
        if isinstance(candidate, dict):
            belief = Belief.from_dict(candidate)
        elif isinstance(candidate, Belief):
            belief = copy.deepcopy(candidate)
        else:
            return {"status": "rejected", "edge_id": None} if return_details else "rejected"

        # Передаём fast_path в Guardian
        if not self.guardian.stage_a_filter(belief, fast_path=fast_path):
            return self._result(belief, return_details)

        if belief.context_flags.get("has_conflict"):
            status = self._resolve_conflict(belief)
            belief.status = status
            return self._result(belief, return_details)

        self._persist(belief)
        return self._result(belief, return_details)

    def _result(self, belief: Belief, return_details: bool):
        if return_details:
            return {"status": belief.status, "edge_id": belief.id}
        return belief.status

    def _compare_confidence(self, old_conf: float, old_type: str, new_conf: float, new_type: str) -> str:
        type_order = {"deductive": 4, "inductive": 3, "analogical": 2, "enthymeme": 1, "manual": 0}
        old_rank = type_order.get(old_type, 0)
        new_rank = type_order.get(new_type, 0)

        if old_rank > new_rank:
            return "old"
        elif new_rank > old_rank:
            return "new"
        else:
            return "new" if new_conf > old_conf else "old"

    def _resolve_conflict(self, belief: Belief) -> str:
        old_id = belief.context_flags.get("conflicting_with_id")
        if not old_id:
            self._persist(belief)
            return belief.status

        old_row = self.db.fetchone(
            "SELECT confidence_score, certainty_type FROM graph_edges WHERE edge_id = ?",
            (old_id,)
        )
        if not old_row:
            self._persist(belief)
            return belief.status

        old_confidence, old_certainty = old_row
        winner = self._compare_confidence(
            old_confidence, old_certainty,
            belief.confidence, belief.certainty_type
        )

        if winner == "old":
            self._persist_in_transaction(belief, old_id, is_superseded=False)
            return "conflicted"
        else:
            self._persist_in_transaction(belief, old_id, is_superseded=True)
            return "active"

    def _persist_in_transaction(self, belief: Belief, old_id: str, is_superseded: bool) -> None:
        try:
            self.db.execute("BEGIN")
            self._persist_raw(belief)
            if belief.id is None:
                raise ValueError("Не удалось получить ID для нового убеждения")

            conflict = Conflict(
                belief_a_id=old_id,
                belief_b_id=belief.id,
                conflict_type="logical_opposition"
            )
            self._persist_conflict(conflict)
            belief.context_flags["conflict_id"] = conflict.id

            if is_superseded:
                self.db.execute("UPDATE graph_edges SET status = 'superseded' WHERE edge_id = ?", (old_id,))
            else:
                self.db.execute("UPDATE graph_edges SET status = 'conflicted' WHERE edge_id = ?", (old_id,))

            self.db.execute("COMMIT")
        except Exception as e:
            try:
                self.db.execute("ROLLBACK")
            except Exception:
                pass
            print(f"[BeliefManager] Ошибка в конфликтной транзакции: {e}")
            belief.status = "error"
            belief.context_flags["persist_error"] = str(e)

    def _persist(self, belief: Belief) -> None:
        try:
            self._persist_raw(belief)
        except Exception as e:
            print(f"[BeliefManager] Ошибка сохранения убеждения: {e}")
            belief.status = "error"
            belief.context_flags["persist_error"] = str(e)

    def _persist_raw(self, belief: Belief) -> None:
        import uuid
        from echo_core.causal_graph import normalize

        for node in belief.context_flags.get("unresolved_nodes", []):
            if isinstance(node, str):
                self.db.execute(
                    "INSERT OR IGNORE INTO graph_nodes (node_id, node_type) VALUES (?, 'unknown')",
                    (normalize(node),)
                )

        edge_id = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO graph_edges
               (edge_id, source_node_id, target_node_id, relation_type, confidence_score,
                certainty_type, status, quantifier, provenance, context_flags_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                edge_id,
                normalize(belief.source),
                normalize(belief.target),
                belief.relation,
                belief.confidence,
                belief.certainty_type,
                belief.status,
                belief.quantifier,
                json.dumps(belief.provenance, ensure_ascii=False),
                json.dumps(belief.context_flags, ensure_ascii=False),
            )
        )
        belief.id = edge_id

    def _persist_conflict(self, conflict: Conflict) -> None:
        try:
            existing = self.db.fetchone(
                "SELECT id FROM graph_conflicts WHERE belief_a_id = ? AND belief_b_id = ?",
                (conflict.belief_a_id, conflict.belief_b_id)
            )
            if existing:
                conflict.id = existing[0]
                return

            self.db.execute(
                "INSERT INTO graph_conflicts (belief_a_id, belief_b_id, conflict_type, resolution_status) VALUES (?, ?, ?, ?)",
                (conflict.belief_a_id, conflict.belief_b_id, conflict.conflict_type, conflict.resolution_status)
            )
            row = self.db.fetchone("SELECT last_insert_rowid()")
            if row:
                conflict.id = row[0]
        except OperationalError:
            print("[BeliefManager] Не удалось сохранить конфликт: таблица graph_conflicts может отсутствовать")


# ======================
if __name__ == "__main__":
    from unittest.mock import Mock
    mock_db = Mock()
    mock_db.fetchone.return_value = None
    mock_db.execute = Mock()

    manager = BeliefManager(mock_db)

    candidate = Belief(source="S", target="P", relation="IS_A", confidence=0.8, provenance={"engine": "test"})
    status = manager.receive(candidate)
    assert status in ("active", "candidate"), f"Ожидался active/candidate, получен {status}"
    print(f"✅ обычное сохранение: {status}")

    # Тест fast_path
    candidate2 = Belief(source="X", target="Y", relation="IS_A", confidence=0.9, provenance={"engine": "external_db"})
    status2 = manager.receive(candidate2, fast_path=True)
    assert status2 in ("active", "candidate"), f"fast_path должен работать, получен {status2}"
    print(f"✅ fast_path: {status2}")

    print("\n🔥 BeliefManager v1.6 OK")