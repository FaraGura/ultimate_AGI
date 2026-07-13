"""Dialectic engine — contradiction detection and resolution."""

from typing import Dict, List, Optional, Tuple


class DialecticEngine:
    def detect_contradiction(self, statements: List[Dict]) -> Optional[Tuple[Dict, Dict]]:
        """
        Find pairs with same subject/predicate but different objects.
        Each statement: {subject, predicate, object, confidence}.
        """
        for i, stmt_a in enumerate(statements):
            for stmt_b in statements[i + 1:]:
                if (
                    stmt_a.get("subject") == stmt_b.get("subject")
                    and stmt_a.get("predicate") == stmt_b.get("predicate")
                    and stmt_a.get("object") != stmt_b.get("object")
                ):
                    return (stmt_a, stmt_b)
        return None

    def resolve(self, thesis: Dict, antithesis: Dict) -> Dict:
        """Return the statement with higher confidence."""
        conf_t = float(thesis.get("confidence", 0.5))
        conf_a = float(antithesis.get("confidence", 0.5))
        return thesis if conf_t >= conf_a else antithesis

    def hybridize(self, precedent_a: Dict, precedent_b: Dict) -> Optional[Dict]:
        """Merge two statements of the same type; average confidence."""
        pred_a = precedent_a.get("predicate") or precedent_a.get("type")
        pred_b = precedent_b.get("predicate") or precedent_b.get("type")
        if pred_a != pred_b:
            return None

        subj_a = precedent_a.get("subject", "")
        subj_b = precedent_b.get("subject", "")
        obj_a = precedent_a.get("object", "")
        obj_b = precedent_b.get("object", "")

        merged_subject = subj_a if subj_a == subj_b else f"{subj_a} и {subj_b}"
        merged_object = obj_a if obj_a == obj_b else f"{obj_a} и {obj_b}"
        avg_conf = (
            float(precedent_a.get("confidence", 0.5))
            + float(precedent_b.get("confidence", 0.5))
        ) / 2.0

        return {
            "subject": merged_subject,
            "predicate": pred_a,
            "object": merged_object,
            "confidence": avg_conf,
        }

    def resonance_bridge(self, concept_a: str, concept_b: str, graph) -> bool:
        """BFS path check between two concepts in the causal graph."""
        return graph.has_path(concept_a, concept_b)