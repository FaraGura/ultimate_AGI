# echo_core/guardian.py
"""
Guardian v2.2 — Детерминированный фильтр логической целостности (Stage A).
Поддерживает как словари, так и объекты Belief.
Добавлена защита от циклической валидации (MAX_VALIDATION_DEPTH).
"""

from typing import Optional, Union
from echo_core.belief import Belief


class Guardian:
    NEGATIONS = {
        "IS_A": "NOT_IS", "NOT_IS": "IS_A",
        "HAS_PROPERTY": "LACKS_PROPERTY", "LACKS_PROPERTY": "HAS_PROPERTY",
        "CAN_DO": "CANNOT_DO", "CANNOT_DO": "CAN_DO",
        "USED_FOR": "NOT_USED_FOR", "NOT_USED_FOR": "USED_FOR",
    }
    MAX_VALIDATION_DEPTH = 5

    def __init__(self, db):
        self.db = db

    def stage_a_filter(self, candidate: Union[dict, Belief]) -> bool:
        if isinstance(candidate, Belief):
            data = candidate.to_dict()
        elif isinstance(candidate, dict):
            data = candidate
        else:
            return False

        data.setdefault("context_flags", {})
        data.setdefault("status", "created")

        if not self._identity_check(data):
            data["status"] = "rejected"
            return False
        if not self._evidence_check(data):
            data["status"] = "rejected"
            return False
        if self._contradiction_check(data):
            data["status"] = "rejected"
            return False

        self._structural_check(data)
        data["status"] = "candidate"
        if isinstance(candidate, Belief):
            candidate.status = data["status"]
            candidate.context_flags = data["context_flags"]
        return True

    def _identity_check(self, data: dict) -> bool:
        source = str(data.get("source", "")).strip()
        target = str(data.get("target", "")).strip()
        return bool(source and target and source != target)

    def _evidence_check(self, data: dict) -> bool:
        try:
            confidence = float(data.get("confidence", 0.0))
        except (ValueError, TypeError):
            return False
        provenance = data.get("provenance")
        if confidence <= 0.0 or not provenance or not isinstance(provenance, dict):
            return False
        if confidence < 0.7:
            data["context_flags"]["low_confidence"] = True
        return True

    def _contradiction_check(self, data: dict, depth: int = 0) -> bool:
        if depth > self.MAX_VALIDATION_DEPTH:
            return False
        relation = data.get("relation") or data.get("relation_type")
        if not relation:
            return False
        opposite = self.NEGATIONS.get(relation)
        if not opposite:
            return False
        source = data.get("source")
        target = data.get("target")
        row = self.db.fetchone(
            "SELECT confidence FROM graph_edges WHERE source_node_id = ? AND target_node_id = ? AND relation_type = ?",
            (source, target, opposite)
        )
        if row:
            existing_conf = float(row[0])
            candidate_conf = float(data.get("confidence", 0.0))
            if existing_conf >= candidate_conf:
                return True
            data["context_flags"]["has_conflict"] = True
            data["context_flags"]["weaker_contradiction_detected"] = True
        return False

    def _structural_check(self, data: dict) -> None:
        source = data.get("source")
        target = data.get("target")
        if not source or not target:
            return
        src_exists = self.db.fetchone("SELECT 1 FROM graph_nodes WHERE node_id = ?", (source,))
        tgt_exists = self.db.fetchone("SELECT 1 FROM graph_nodes WHERE node_id = ?", (target,))
        if not src_exists or not tgt_exists:
            data["context_flags"]["unresolved_nodes"] = [source] if not src_exists else []
            if not tgt_exists:
                data["context_flags"]["unresolved_nodes"].append(target)
            data["context_flags"]["hypothesis"] = True


# ======================
if __name__ == "__main__":
    from unittest.mock import Mock
    mock_db = Mock()
    g = Guardian(mock_db)
    assert g.stage_a_filter({"source":"S","target":"P","relation":"IS_A","confidence":0.8,"provenance":{"e":"t"}})
    assert not g.stage_a_filter({"source":"A","target":"A","relation":"IS_A"})
    print("✅ Guardian v2.2 OK")