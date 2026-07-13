# echo_core/ontology.py
"""
Ontology v1.0 — операции с понятиями.
Реализует:
- Ограничение (переход от общего к частному)
- Обобщение (переход от частного к общему)
- Определение (раскрытие содержания понятия)
- Деление (раскрытие объёма понятия)

Работает с graph_nodes и graph_edges через DatabaseManager.
Без LLM, чистая детерминированная логика.
"""

from typing import Optional, Dict, List


class Ontology:
    """
    Движок операций над понятиями.
    """

    def __init__(self, db):
        self.db = db

    # ── ОГРАНИЧЕНИЕ ───────────────────────────────────────────────
    def restrict(self, concept_id: str, attribute: str, value: str) -> Optional[dict]:
        """
        Переход от общего к частному: добавляет признак к понятию.
        Результат — новое, более конкретное понятие.
        """
        # Проверяем, существует ли исходное понятие
        existing = self.db.fetchone("SELECT payload FROM graph_nodes WHERE node_id = ?", (concept_id,))
        if not existing:
            return None

        # Создаём новое понятие с дополнительным признаком
        import json
        try:
            payload = json.loads(existing[0]) if existing[0] else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}

        new_id = f"{concept_id}_restricted_{attribute}_{value}"
        new_payload = {**payload, attribute: value}

        self.db.execute(
            "INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload) VALUES (?, 'concept', ?)",
            (new_id, json.dumps(new_payload))
        )

        # Связываем: новое понятие — это частный случай исходного
        self.db.execute(
            "INSERT OR IGNORE INTO graph_edges (source_node_id, target_node_id, relation_type) VALUES (?, ?, 'IS_A')",
            (new_id, concept_id)
        )

        return {
            "node_id": new_id,
            "parent_id": concept_id,
            "attribute": attribute,
            "value": value,
            "payload": new_payload,
        }

    # ── ОБОБЩЕНИЕ ─────────────────────────────────────────────────
    def generalize(self, concept_ids: List[str], common_label: str = None) -> Optional[dict]:
        """
        Переход от частного к общему: находит общий родительский класс.
        Если не найден — создаёт новый.
        """
        if not concept_ids:
            return None

        # Ищем общий класс среди родителей
        parent_sets = []
        for cid in concept_ids:
            rows = self.db.fetchall(
                "SELECT target_node_id FROM graph_edges WHERE source_node_id = ? AND relation_type = 'IS_A'",
                (cid,)
            )
            parents = {row[0] for row in rows}
            if not parents:
                return None
            parent_sets.append(parents)

        # Пересечение всех множеств — общие родители
        common_parents = parent_sets[0]
        for ps in parent_sets[1:]:
            common_parents = common_parents & ps

        if common_parents:
            return {"general_class_id": common_parents.pop(), "members": concept_ids}

        # Если общего родителя нет — создаём новый
        if not common_label:
            return None

        import json
        self.db.execute(
            "INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload) VALUES (?, 'concept', ?)",
            (common_label, json.dumps({"members": concept_ids}))
        )

        for cid in concept_ids:
            self.db.execute(
                "INSERT OR IGNORE INTO graph_edges (source_node_id, target_node_id, relation_type) VALUES (?, ?, 'IS_A')",
                (cid, common_label)
            )

        return {"general_class_id": common_label, "members": concept_ids}

    # ── ОПРЕДЕЛЕНИЕ ──────────────────────────────────────────────
    def define(self, concept_id: str) -> Optional[dict]:
        """
        Раскрывает содержание понятия: возвращает его признаки и родительские классы.
        """
        # Признаки (свойства)
        properties = self.db.fetchall(
            "SELECT relation_type, target_node_id FROM graph_edges WHERE source_node_id = ? AND relation_type IN ('HAS_PROPERTY', 'CAN_DO', 'USED_FOR')",
            (concept_id,)
        )
        # Родительские классы
        parents = self.db.fetchall(
            "SELECT target_node_id FROM graph_edges WHERE source_node_id = ? AND relation_type = 'IS_A'",
            (concept_id,)
        )

        return {
            "concept_id": concept_id,
            "properties": {row[0]: row[1] for row in properties},
            "parent_classes": [row[0] for row in parents],
        }

    # ── ДЕЛЕНИЕ ───────────────────────────────────────────────────
    def divide(self, concept_id: str) -> Optional[dict]:
        """
        Раскрывает объём понятия: возвращает все частные случаи (подклассы).
        """
        subclasses = self.db.fetchall(
            "SELECT source_node_id FROM graph_edges WHERE target_node_id = ? AND relation_type = 'IS_A'",
            (concept_id,)
        )

        if not subclasses:
            return None

        return {
            "concept_id": concept_id,
            "subclasses": [row[0] for row in subclasses],
        }


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock

    mock_db = Mock()
    ontology = Ontology(mock_db)

    # Тест 1: Ограничение — создание частного понятия
    mock_db.fetchone.return_value = ('{"color": "red"}',)
    result = ontology.restrict("apple", "size", "big")
    assert result is not None
    assert "apple_restricted" in result["node_id"]
    print("✅ Тест 1 (ограничение) пройден")

    # Тест 2: Обобщение — общий родитель найден
    mock_db.fetchall.side_effect = [
        [("fruit",)],  # родители яблока
        [("fruit",)],  # родители груши
    ]
    result = ontology.generalize(["apple", "pear"])
    assert result is not None
    assert result["general_class_id"] == "fruit"
    print("✅ Тест 2 (обобщение) пройден")

    # Тест 3: Определение — свойства понятия
    mock_db.fetchall.side_effect = [
        [("HAS_PROPERTY", "red"), ("CAN_DO", "grow")],  # свойства
        [("fruit",)],                                   # родители
    ]
    result = ontology.define("apple")
    assert result is not None
    assert "red" in result["properties"].values()
    print("✅ Тест 3 (определение) пройден")

    # Тест 4: Деление — подклассы
    mock_db.fetchall.return_value = [("apple",), ("pear",), ("banana",)]
    result = ontology.divide("fruit")
    assert result is not None
    assert len(result["subclasses"]) == 3
    print("✅ Тест 4 (деление) пройден")

    print("\n🔥 Все тесты Ontology пройдены.")