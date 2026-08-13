from echo_core.knowledge_extractor import KnowledgeExtractor


class DummyGraph:
    logger = None


class DummyDB:
    pass


def test_extract_all_collects_bulleted_properties_and_actions():
    extractor = KnowledgeExtractor(DummyGraph(), DummyDB())
    text = """
Яблоко — это фрукт.

**Свойства:**
* Сладкое и сочное.
- Красное.
1. Может быть съедено.
* Служит для питания.
***
### Дополнительно
"""

    facts = extractor.extract_all(text)

    assert any(
        fact["subject"] == "Яблоко" and fact["relation"] == "HAS_PROPERTY" and fact["object"] == "Сладкое и сочное"
        for fact in facts
    )
    assert any(
        fact["subject"] == "Яблоко" and fact["relation"] == "HAS_PROPERTY" and fact["object"] == "Красное"
        for fact in facts
    )
    assert any(
        fact["subject"] == "Яблоко" and fact["relation"] == "CAN_DO" and fact["object"] == "Может быть съедено"
        for fact in facts
    )
    assert any(
        fact["subject"] == "Яблоко" and fact["relation"] == "CAN_DO" and fact["object"] == "Служит для питания"
        for fact in facts
    )
    assert not any(fact["object"] == "Свойства" for fact in facts)
