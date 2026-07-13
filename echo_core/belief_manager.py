# echo_core/belief_manager.py
"""
BeliefManager v1.4 — менеджер убеждений.
Принимает словари или объекты Belief, прогоняет через Guardian,
разрешает конфликты, сохраняет в базу.
Исправления v1.4:
- Разделены _persist() и _persist_raw() для транзакций
- ROLLBACK обёрнут в try/except
- Порядок операций в конфликте: INSERT new → INSERT conflict → UPDATE old
- Тест на deepcopy
- _persist_conflict ловит только OperationalError
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

    def receive(self, candidate: Union[dict, Belief]) -> str:
        if isinstance(candidate, dict):
            belief = Belief.from_dict(candidate)
        elif isinstance(candidate, Belief):
            belief = copy.deepcopy(candidate)
        else:
            return "rejected"

        if not self.guardian.stage_a_filter(belief):
            return belief.status

        if belief.context_flags.get("has_conflict"):
            return self._resolve_conflict(belief)

        self._persist(belief)
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
            "SELECT confidence, certainty_type FROM graph_edges WHERE id = ?",
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

    def _persist_in_transaction(self, belief: Belief, old_id: int, is_superseded: bool) -> None:
        """Сохраняет убеждение и обновляет старое в одной транзакции.
        Порядок: INSERT new → INSERT conflict → UPDATE old."""
        try:
            self.db.execute("BEGIN")
            self._persist_raw(belief)
            if belief.id is None:
                raise ValueError("Не удалось получить ID для нового убеждения")

            # Сначала фиксируем конфликт, потом меняем состояние старого знания
            conflict = Conflict(
                belief_a_id=old_id,
                belief_b_id=belief.id,
                conflict_type="logical_opposition"
            )
            self._persist_conflict(conflict)
            belief.context_flags["conflict_id"] = conflict.id

            if is_superseded:
                self.db.execute("UPDATE graph_edges SET status = 'superseded' WHERE id = ?", (old_id,))
            else:
                self.db.execute("UPDATE graph_edges SET status = 'conflicted' WHERE id = ?", (old_id,))

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
        """Сохраняет убеждение с обработкой ошибок."""
        try:
            self._persist_raw(belief)
        except Exception as e:
            print(f"[BeliefManager] Ошибка сохранения убеждения: {e}")
            belief.status = "error"
            belief.context_flags["persist_error"] = str(e)

    def _persist_raw(self, belief: Belief) -> None:
        """Сохраняет убеждение без обработки ошибок. Для использования внутри транзакций."""
        for node in belief.context_flags.get("unresolved_nodes", []):
            if isinstance(node, str):
                self.db.execute(
                    "INSERT OR IGNORE INTO graph_nodes (node_id, node_type) VALUES (?, 'unknown')",
                    (node,)
                )

        self.db.execute(
            """INSERT INTO graph_edges
               (source_node_id, target_node_id, relation_type, confidence_score,
                certainty_type, status, quantifier, provenance, context_flags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                belief.source,
                belief.target,
                belief.relation,
                belief.confidence,
                belief.certainty_type,
                belief.status,
                belief.quantifier,
                json.dumps(belief.provenance, ensure_ascii=False),
                json.dumps(belief.context_flags, ensure_ascii=False),
            )
        )

        # TODO: при переходе на асинхронную БД заменить на INSERT ... RETURNING id
        row = self.db.fetchone("SELECT last_insert_rowid()")
        if row:
            belief.id = row[0]

    def _persist_conflict(self, conflict: Conflict) -> None:
        """Сохраняет конфликт. Ловит только OperationalError."""
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
            print(f"[BeliefManager] Не удалось сохранить конфликт: таблица graph_conflicts может отсутствовать")


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock

    mock_db = Mock()
    mock_db.fetchone.return_value = None
    mock_db.execute = Mock()

    manager = BeliefManager(mock_db)

    # Тест 1: Чистое убеждение
    candidate = Belief(source="S", target="P", relation="IS_A", confidence=0.8, provenance={"engine": "test"})
    status = manager.receive(candidate)
    assert status in ("active", "candidate"), f"Ожидался active/candidate, получен {status}"
    print(f"✅ Тест 1 (чистое убеждение) пройден, статус: {status}")

    # Тест 2: Слабое без provenance
    candidate = Belief(source="A", target="B", relation="IS_A", confidence=0.3)
    status = manager.receive(candidate)
    assert status == "rejected", f"Ожидался rejected, получен {status}"
    print(f"✅ Тест 2 (слабое без provenance) пройден, статус: {status}")

    # Тест 3: Сравнение дедукций
    assert manager._compare_confidence(0.8, "deductive", 0.99, "deductive") == "new"
    assert manager._compare_confidence(0.8, "deductive", 0.7, "deductive") == "old"
    assert manager._compare_confidence(0.5, "inductive", 0.9, "deductive") == "new"
    print("✅ Тест 3 (сравнение дедукций) пройден")

    # Тест 4: Deepcopy защищает исходный объект от мутации
    original = Belief(source="A", target="B", relation="IS_A", confidence=0.8, provenance={"engine": "test"})
    manager.receive(original)
    assert "has_conflict" not in original.context_flags, "Исходный Belief был мутирован!"
    print("✅ Тест 4 (deepcopy защита) пройден")

    print("\n🔥 Все тесты BeliefManager v1.4 пройдены.")