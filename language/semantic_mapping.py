# language/semantic_mapping.py
"""
Semantic Mapping v1.0 — связывает языковые символы (Language Kernel)
с концептами в CausalGraph. Одно слово может указывать на несколько концептов.
Контекст выбирает правильный.
"""

from typing import List, Optional


class SemanticMapper:
    """Прослойка между словами и концептами графа."""

    def __init__(self, db, embedder):
        self.db = db
        self.embedder = embedder

    def word_to_concepts(self, word: str, limit: int = 5) -> List[str]:
        """
        По слову находит ближайшие концепты в graph_nodes.
        Использует эмбеддинги, если доступны, иначе — поиск по ключу.
        """
        # Сначала ищем точное совпадение среди символов Language Kernel
        rows = self.db.fetchall(
            """SELECT node_id FROM graph_nodes
               WHERE node_type IN ('symbol', 'concept')
                 AND json_extract(payload, '$.value') = ?""",
            (word.lower(),)
        )
        if rows:
            return [row[0] for row in rows]

        # Если точного совпадения нет — ищем ближайшие через эмбеддинги
        if self.embedder.model:
            all_concepts = self.db.fetchall(
                "SELECT node_id, payload FROM graph_nodes WHERE node_type IN ('symbol', 'concept')"
            )
            if not all_concepts:
                return []
            import json
            candidates = [(row[0], json.loads(row[1]).get('value', '')) for row in all_concepts]
            word_emb = self.embedder.get_embedding(word)
            if word_emb is not None:
                scored = []
                for node_id, text in candidates:
                    if text:
                        emb = self.embedder.get_embedding(text)
                        if emb is not None:
                            import numpy as np
                            sim = np.dot(word_emb, emb) / (np.linalg.norm(word_emb) * np.linalg.norm(emb) + 1e-8)
                            scored.append((node_id, sim))
                scored.sort(key=lambda x: x[1], reverse=True)
                return [node_id for node_id, _ in scored[:limit]]

        return []

    def concept_to_words(self, concept_id: str) -> List[str]:
        """
        По концепту находит связанные языковые символы.
        """
        rows = self.db.fetchall(
            """SELECT n.node_id, n.payload
               FROM graph_nodes n
               JOIN graph_edges e ON (e.source_node_id = n.node_id OR e.target_node_id = n.node_id)
               WHERE (e.source_node_id = ? OR e.target_node_id = ?)
                 AND n.node_type = 'symbol'
                 AND n.node_id != ?""",
            (concept_id, concept_id, concept_id)
        )
        import json
        return [json.loads(row[1]).get('value', row[0]) for row in rows]

    def resolve_context(self, word: str, context_flags: int = 1) -> Optional[str]:
        """
        Выбирает один концепт для слова в заданном контексте.
        """
        concepts = self.word_to_concepts(word)
        if not concepts:
            return None
        # Если контекст GLOBAL (1) — возвращаем первый попавшийся
        if context_flags == 1:
            return concepts[0]
        # Для DEVICE или EXPERIENCE — ищем узел с соответствующим context_flags
        for cid in concepts:
            row = self.db.fetchone(
                "SELECT context_flags FROM graph_nodes WHERE node_id = ?",
                (cid,)
            )
            if row and (row[0] & context_flags):
                return cid
        return concepts[0]


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    from unittest.mock import Mock
    import json

    mock_db = Mock()
    mock_db.fetchall.return_value = [
        ("symbol_self", json.dumps({"value": "я"})),
        ("symbol_system", json.dumps({"value": "система"}))
    ]
    mock_embedder = Mock()
    mock_embedder.model = None

    mapper = SemanticMapper(mock_db, mock_embedder)

    words = mapper.word_to_concepts("я")
    assert len(words) == 2, f"Ожидалось 2 символа, получено {len(words)}"
    print("✅ Тест word_to_concepts пройден")

    mock_db.fetchall.return_value = []
    words = mapper.word_to_concepts("неизвестное_слово")
    assert len(words) == 0
    print("✅ Тест неизвестного слова пройден")

    print("\n🔥 Все тесты SemanticMapper пройдены.")