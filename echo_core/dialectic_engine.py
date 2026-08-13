# echo_core/dialectic_engine.py
"""Dialectic engine — contradiction detection, resolution, and disambiguation.

v2 (Claude): disambiguate() переписан. Раньше метод сканировал ВСЕ рёбра
с данным (source, relation) и слепо раскидывал их по разным sense_id —
из-за этого совместимые факты (например "кошка HAS_PROPERTY шерсть" и
"кошка HAS_PROPERTY четыре лапы" — оба верны одновременно, не омонимы!)
ложно расщеплялись на разные "смыслы". Теперь метод принимает ЯВНЫЙ
список edge_id, которые Guardian.find_homonym_candidates() уже определил
как реальных кандидатов на разные смыслы — и размечает только их, не
трогая остальные рёбра того же субъекта.
"""

import json
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

    # =====================================================================
    # disambiguate — размечает СМЫСЛЫ только явно конфликтующих рёбер.
    # =====================================================================
    def disambiguate(self, db, new_edge_id: str,
                      conflicting_edge_ids: List[str]) -> int:
        """
        Назначает sense_id только рёбрам из явного списка:
        new_edge_id (только что созданное ребро) + conflicting_edge_ids
        (то, что Guardian.find_homonym_candidates() определил как реальных
        кандидатов на разные смыслы). Остальные рёбра того же субъекта
        не трогаются вообще — они не участвовали в конфликте.

        Если у части рёбер из списка уже есть sense_id (например, при
        добавлении третьего значения слова) — новым рёбрам назначается
        следующий свободный номер, существующие не меняются.

        Возвращает максимальный использованный sense_id, или 0, если
        разметка не потребовалась (список пуст или содержит < 2 рёбер).
        """
        all_edge_ids = list(dict.fromkeys(conflicting_edge_ids + [new_edge_id]))
        if len(all_edge_ids) < 2:
            return 0

        placeholders = ",".join("?" for _ in all_edge_ids)
        rows = db.fetchall(
            f"SELECT edge_id, provenance FROM graph_edges WHERE edge_id IN ({placeholders})",
            tuple(all_edge_ids)
        )

        existing_senses = set()
        edges_without_sense = []

        for edge_id, provenance_blob in rows:
            try:
                prov = json.loads(provenance_blob) if provenance_blob else {}
            except (json.JSONDecodeError, TypeError):
                prov = {}
            sense = prov.get("sense_id")
            if sense is not None:
                existing_senses.add(int(sense))
            else:
                edges_without_sense.append((edge_id, prov))

        if not edges_without_sense:
            return max(existing_senses) if existing_senses else 0

        next_sense = 1
        for edge_id, prov in edges_without_sense:
            while next_sense in existing_senses:
                next_sense += 1
            prov["sense_id"] = next_sense
            db.execute(
                "UPDATE graph_edges SET provenance = ? WHERE edge_id = ?",
                (json.dumps(prov, ensure_ascii=False), edge_id)
            )
            existing_senses.add(next_sense)

        return max(existing_senses)
