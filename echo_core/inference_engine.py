# echo_core/inference_engine.py
"""
Inference Engine v3.3 — Производственное ядро умозаключений для Echo Core.
Поддерживает когнитивный вывод на базе детерминированной формальной логики:
- Дедукция (Категорические силлогизмы через автоинициализируемый SyllogismEngine)
- Индукция (Вероятностное обобщение с полной трассировкой первичных наблюдений)
- Аналогический перенос (С фильтрацией поверхностных/нерелевантных признаков)
- Энтимемы (Восстановление пропущенных посылок через средний термин M)

Защиты и валидация графа:
- Изолированный DFS (через visited.copy()) для точного поиска циклов
- Защита от тавтологии (А -> А) и дублирования физических ребер
- Единый реестр типов уверенности CERTAINTY_TYPES

v3.3: Все SQL-запросы приведены к реальной схеме graph_edges
      (source_node_id, target_node_id, edge_id, confidence_score).
"""

from typing import Optional, Dict, List, Tuple
from echo_core.syllogism_engine import SyllogismEngine


class InferenceEngine:
    # Централизованный реестр типов определенности вывода
    CERTAINTY_TYPES = {
        "DEDUCTIVE": "deductive",
        "INDUCTIVE": "inductive",
        "ANALOGICAL": "analogical",
        "ENTHYMEME": "enthymeme",
    }

    # Поверхностные/нерелевантные признаки, запрещенные для автоматического переноса по аналогии
    NON_TRANSFERABLE_PROPERTIES = {
        "цвет", "название", "идентификатор", "имя", "дата", "координаты"
    }

    def __init__(self, db, syllogism_engine=None, guardian=None):
        self.db = db
        self.syllogism = syllogism_engine or SyllogismEngine(db)
        self.guardian = guardian

    # ── Дедукция ─────────────────────────────────────────────────
    def deduce(self, premise1: dict, premise2: dict) -> Optional[dict]:
        """Прямой дедуктивный вывод из двух посылок с валидацией графа."""
        conclusion = self.syllogism.deduce(premise1, premise2)
        if conclusion is None:
            return None

        if self._is_trivial(conclusion) or self._edge_exists(conclusion) or self._creates_cycle(conclusion):
            return None
        if self.guardian and not self.guardian.stage_a_filter(conclusion):
            return None

        conclusion["certainty_type"] = self.CERTAINTY_TYPES["DEDUCTIVE"]
        conclusion.setdefault("confidence", 1.0)
        conclusion.setdefault("provenance", {})
        conclusion["provenance"]["engine"] = "inference_engine"
        conclusion["provenance"]["method"] = "deduction"
        conclusion["provenance"]["parents"] = [
            {"id": premise1.get("id"), "source": premise1.get("source"), "target": premise1.get("target")},
            {"id": premise2.get("id"), "source": premise2.get("source"), "target": premise2.get("target")},
        ]
        conclusion.setdefault("context_flags", {})
        conclusion["context_flags"]["cycle_checked"] = True
        return conclusion

    # ── Индукция ─────────────────────────────────────────────────
    def induce(self, observations: List[dict], target_class: str = None) -> Optional[dict]:
        """Индуктивное обобщение частных фактов с полным сохранением связей с родителями."""
        if len(observations) < 2:
            return None

        predicates = set(obs.get("target") for obs in observations)
        if len(predicates) != 1:
            return None

        predicate = predicates.pop()
        subjects = [obs.get("source") for obs in observations if obs.get("source")]
        if not subjects:
            return None

        if target_class is None:
            target_class = self._find_common_class(subjects)
        if not target_class:
            return None

        confidence = min(0.9, 0.5 + (len(observations) * 0.05))

        conclusion = {
            "source": target_class,
            "target": predicate,
            "relation": "induced",
            "quantifier": "some",
            "confidence": confidence,
            "certainty_type": self.CERTAINTY_TYPES["INDUCTIVE"],
            "provenance": {
                "engine": "inference_engine",
                "method": "induction",
                "sample_size": len(observations),
                "parents": [obs.get("id") for obs in observations if obs.get("id")],
                "subjects": subjects[:5],
            },
            "context_flags": {"hypothesis": True, "cycle_checked": True},
        }

        if self._is_trivial(conclusion) or self._edge_exists(conclusion) or self._creates_cycle(conclusion):
            return None
        if self.guardian and not self.guardian.stage_a_filter(conclusion):
            return None
        return conclusion

    def _find_common_class(self, subjects: List[str]) -> Optional[str]:
        for subject in subjects:
            row = self.db.fetchone(
                "SELECT target_node_id FROM graph_edges WHERE source_node_id = ? AND relation_type = 'IS_A' LIMIT 1",
                (subject,)
            )
            if row:
                class_name = row[0]
                if all(
                    self.db.fetchone(
                        "SELECT 1 FROM graph_edges WHERE source_node_id = ? AND target_node_id = ? AND relation_type = 'IS_A'",
                        (s, class_name)
                    )
                    for s in subjects
                ):
                    return class_name
        return None

    # ── Аналогия ─────────────────────────────────────────────────
    def analogize(self, source_obj: str, target_obj: str) -> List[dict]:
        """Перенос признаков по аналогии с фильтрацией поверхностных свойств."""
        source_props = self._get_properties(source_obj)
        target_props = self._get_properties(target_obj)

        source_pairs = {(prop, val) for prop, values in source_props.items() for val in values}
        target_pairs = {(prop, val) for prop, values in target_props.items() for val in values}

        if not source_pairs and not target_pairs:
            return []

        common = source_pairs & target_pairs
        total = max(len(source_pairs), len(target_pairs))
        similarity = len(common) / total if total > 0 else 0.0

        if similarity < 0.5:
            return []

        hypotheses = []
        for (prop, value) in source_pairs:
            if prop in self.NON_TRANSFERABLE_PROPERTIES:
                continue

            if (prop, value) not in target_pairs:
                hypothesis = {
                    "source": target_obj,
                    "target": value,
                    "relation": prop,
                    "quantifier": "some",
                    "confidence": round(0.5 + (similarity * 0.1), 2),
                    "certainty_type": self.CERTAINTY_TYPES["ANALOGICAL"],
                    "provenance": {
                        "engine": "inference_engine",
                        "method": "analogy",
                        "analogue": source_obj,
                        "similarity": round(similarity, 2),
                    },
                    "context_flags": {"hypothesis": True, "cycle_checked": True},
                }

                if self._is_trivial(hypothesis) or self._edge_exists(hypothesis) or self._creates_cycle(hypothesis):
                    continue
                if self.guardian and not self.guardian.stage_a_filter(hypothesis):
                    continue
                hypotheses.append(hypothesis)
        return hypotheses

    def _get_properties(self, node_id: str) -> Dict[str, List[str]]:
        rows = self.db.fetchall(
            "SELECT relation_type, target_node_id FROM graph_edges WHERE source_node_id = ?",
            (node_id,)
        )
        props = {}
        for row in rows:
            props.setdefault(row[0], []).append(row[1])
        return props

    # ── Энтимемы ─────────────────────────────────────────────────
    def resolve_enthymeme(self, premise: dict, conclusion: dict) -> Optional[dict]:
        premise_terms = {premise.get("source"), premise.get("target")}
        conclusion_terms = {conclusion.get("source"), conclusion.get("target")}
        middle_terms = premise_terms - conclusion_terms

        if not middle_terms:
            return None

        middle = middle_terms.pop()

        candidates = self.db.fetchall(
            "SELECT edge_id, source_node_id, target_node_id, relation_type, quantifier, confidence_score FROM graph_edges WHERE source_node_id = ? OR target_node_id = ?",
            (middle, middle)
        )

        for edge_id, src, tgt, rel, q, conf in candidates:
            candidate = {
                "id": edge_id,
                "source": src,
                "target": tgt,
                "relation": rel,
                "quantifier": q,
                "confidence": conf,
            }
            
            for p1, p2 in [(candidate, premise), (premise, candidate)]:
                result = self.deduce(p1, p2)
                if result and result.get("source") == conclusion.get("source") and result.get("target") == conclusion.get("target"):
                    candidate["certainty_type"] = self.CERTAINTY_TYPES["ENTHYMEME"]
                    candidate["provenance"] = {
                        "engine": "inference_engine",
                        "method": "enthymeme_resolution",
                        "middle_term": middle,
                        "target_conclusion": {"source": conclusion.get("source"), "target": conclusion.get("target")}
                    }
                    return candidate
        return None

    # ── Защиты Графа ───────────────────────────────────────────
    def _is_trivial(self, conclusion: dict) -> bool:
        return conclusion.get("source") == conclusion.get("target")

    def _edge_exists(self, conclusion: dict) -> bool:
        row = self.db.fetchone(
            "SELECT 1 FROM graph_edges WHERE source_node_id = ? AND target_node_id = ? AND relation_type = ?",
            (conclusion.get("source"), conclusion.get("target"), conclusion.get("relation"))
        )
        return row is not None

    def _creates_cycle(self, new_edge: dict) -> bool:
        return self._path_exists(new_edge.get("target"), new_edge.get("source"))

    def _path_exists(self, start: str, end: str, max_depth: int = 5, visited: set = None) -> bool:
        """Поиск пути в глубину (DFS) с полной изоляцией веток через visited.copy()."""
        if visited is None:
            visited = set()

        if start == end:
            return True
        if max_depth <= 0 or start in visited:
            return False

        visited.add(start)
        neighbours = self.db.fetchall(
            "SELECT target_node_id FROM graph_edges WHERE source_node_id = ?",
            (start,)
        )
        for (nxt,) in neighbours:
            if self._path_exists(nxt, end, max_depth - 1, visited.copy()):
                return True
        return False


# =====================================================================
# ВСТРОЕННЫЕ ТЕСТЫ (v3.3 — Проверка индукции и гибридного init)
# =====================================================================
if __name__ == "__main__":
    from unittest.mock import Mock

    mock_syllogism = Mock()
    mock_syllogism.deduce.return_value = {
        "source": "Сократ",
        "target": "смертны",
        "relation": "deduced",
        "quantifier": "all",
    }

    mock_db = Mock()
    mock_db.fetchone.return_value = None
    mock_db.fetchall.return_value = []

    engine = InferenceEngine(db=mock_db, syllogism_engine=mock_syllogism)

    p1 = {"id": 10, "source": "люди", "target": "смертны", "relation": "IS_A"}
    p2 = {"id": 11, "source": "Сократ", "target": "люди", "relation": "IS_A"}
    result = engine.deduce(p1, p2)
    assert result is not None
    assert result["certainty_type"] == "deductive"
    print("✅ Тест 1 (Гибридный __init__ и Дедукция v3.3) пройден")

    observations = [
        {"id": 501, "source": "Петя", "target": "играть", "relation": "LOVES"},
        {"id": 502, "source": "Ваня", "target": "играть", "relation": "LOVES"},
    ]
    result = engine.induce(observations, target_class="дети")
    assert result is not None
    assert result["certainty_type"] == "inductive"
    assert 501 in result["provenance"]["parents"]
    assert 502 in result["provenance"]["parents"]
    print("✅ Тест 2 (Индукция v3.3 с трекингом parents) пройден")

    print("\n🔥 Модуль echo_core/inference_engine.py v3.3 полностью готов.")