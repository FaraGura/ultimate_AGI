# echo_core/guardian.py
from typing import List, Optional, Union
from echo_core.belief import Belief
from echo_core.causal_graph import normalize


class Guardian:
    NEGATIONS = {
        "IS_A": "NOT_IS", "NOT_IS": "IS_A",
        "HAS_PROPERTY": "LACKS_PROPERTY", "LACKS_PROPERTY": "HAS_PROPERTY",
        "CAN_DO": "CANNOT_DO", "CANNOT_DO": "CAN_DO",
        "USED_FOR": "NOT_USED_FOR", "NOT_USED_FOR": "USED_FOR",
    }
    MAX_VALIDATION_DEPTH = 5

    SOURCE_WEIGHTS = {
        "core_law": 1.2,
        "user_teaching": 1.0,
        "external_db": 1.1,
        "local_llm_teacher": 0.8,
    }

    HOMONYM_MIN_CONFIDENCE = 0.5
    HOMONYM_MAX_CONFIDENCE_DIFF = 0.2

    def __init__(self, db):
        self.db = db

    def stage_a_filter(self, candidate: Union[dict, Belief],
                       fast_path: bool = False) -> bool:
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

        # Тяжёлые проверки пропускаются для доверенных источников
        if not fast_path:
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
            "SELECT confidence_score FROM graph_edges WHERE source_node_id = ? AND target_node_id = ? AND relation_type = ?",
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

    def find_homonym_candidates(self, source: str, relation: str,
                                 target: str, confidence: float) -> List[str]:
        if confidence < self.HOMONYM_MIN_CONFIDENCE:
            return []

        source_norm = normalize(source)
        target_norm = normalize(target)

        rows = self.db.fetchall(
            "SELECT edge_id, target_node_id, confidence_score FROM graph_edges WHERE source_node_id = ? AND relation_type = ? AND target_node_id != ?",
            (source_norm, relation, target_norm)
        )

        candidates = []
        for edge_id, existing_target, existing_conf in rows:
            existing_conf = float(existing_conf or 0.0)
            if existing_conf < self.HOMONYM_MIN_CONFIDENCE:
                continue
            if abs(confidence - existing_conf) < self.HOMONYM_MAX_CONFIDENCE_DIFF:
                candidates.append(edge_id)
        return candidates

    def _structural_check(self, data: dict) -> None:
        source = data.get("source")
        target = data.get("target")
        if not source or not target:
            return
        source_norm = normalize(source)
        target_norm = normalize(target)
        src_exists = self.db.fetchone("SELECT 1 FROM graph_nodes WHERE node_id = ?", (source_norm,))
        tgt_exists = self.db.fetchone("SELECT 1 FROM graph_nodes WHERE node_id = ?", (target_norm,))
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
    assert g.stage_a_filter({"source": "S", "target": "P", "relation": "IS_A", "confidence": 0.8, "provenance": {"e": "t"}})
    assert not g.stage_a_filter({"source": "A", "target": "A", "relation": "IS_A"})

    # Тест fast_path: пропускает _contradiction_check
    mock_db.fetchone.return_value = (0.9,)  # якобы существующее противоречие
    result = g.stage_a_filter({"source": "X", "target": "Y", "relation": "IS_A", "confidence": 0.8, "provenance": {"e": "t"}},
                              fast_path=True)
    assert result, "fast_path должен пропустить contradiction"
    print("✅ fast_path пропускает _contradiction_check")

    # Тест: без fast_path противоречие отклоняется
    result_normal = g.stage_a_filter({"source": "X", "target": "Y", "relation": "IS_A", "confidence": 0.8, "provenance": {"e": "t"}},
                                     fast_path=False)
    assert not result_normal, "без fast_path должно быть rejected"
    print("✅ обычный путь отклоняет противоречие")

    print("\n🔥 Guardian v2.5 OK")