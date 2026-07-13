# language/logic_parser.py

"""
Logic Parser v2.0

Детерминированный парсер категорических суждений.
Извлекает:
- субъект
- предикат
- тип связи
- квантор

Совместим с SyllogismEngine.
"""

import re
from typing import Dict, Optional


class LogicParser:

    def __init__(self):

        self.quantifiers = {
            "ни один": "no",
            "не каждый": "some_not",
            "не все": "some_not",
            "каждый": "all",
            "любой": "all",
            "всякий": "all",
            "все": "all",
            "некоторые": "some",
            "несколько": "some",
            "многие": "some",
        }

        self.copula_patterns = [
            (r"\bне\s+являются\b", "NOT_IS"),
            (r"\bне\s+является\b", "NOT_IS"),
            (r"\bне\s+есть\b", "NOT_IS"),

            (r"\bявляются\b", "IS_A"),
            (r"\bявляется\b", "IS_A"),
            (r"\bесть\b", "IS_A"),
            (r"\bэто\b", "IS_A"),

            (r"\s+[—–-]\s+", "IS_A"),
        ]


    def parse(self, sentence: str) -> Optional[Dict[str, str]]:

        if not sentence:
            return None

        text = sentence.lower().strip()

        quantifier, text = self._extract_quantifier(text)

        relation, subject, predicate = self._extract_copula(text)

        if not subject or not predicate:
            return None

        subject = self._clean(subject)
        predicate = self._clean(predicate)

        if not subject or not predicate:
            return None

        return {
            "source": subject,
            "target": predicate,
            "relation": relation,
            "quantifier": quantifier,
            "confidence": 1.0,
        }


    def _extract_quantifier(self, text: str):

        for word, value in sorted(
            self.quantifiers.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if text.startswith(word):

                remainder = text[len(word):].strip()
                return value, remainder

        return "all", text



    def _extract_copula(self, text: str):

        text = text.strip()


        # Отрицание без явной связки:
        # "кит не рыба"
        negative = re.search(r"\s+не\s+", text)

        if negative:

            left = text[:negative.start()]
            right = text[negative.end():]

            return (
                "NOT_IS",
                left,
                right
            )


        for pattern, relation in self.copula_patterns:

            match = re.search(pattern, text)

            if match:

                subject = text[:match.start()]
                predicate = text[match.end():]

                return (
                    relation,
                    subject,
                    predicate
                )


        # Скрытая связка:
        # "люди смертны"
        parts = text.split(maxsplit=1)

        if len(parts) == 2:

            return (
                "IS_A",
                parts[0],
                parts[1]
            )


        return (
            None,
            None,
            None
        )



    def _clean(self, value: str):

        value = value.strip()

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        value = value.rstrip(".,!?")

        return value



# ======================
# TESTS
# ======================

if __name__ == "__main__":

    parser = LogicParser()


    result = parser.parse(
        "Все люди смертны"
    )

    assert result["source"] == "люди"
    assert result["target"] == "смертны"
    assert result["quantifier"] == "all"

    print("✅ Тест 1 пройден")


    result = parser.parse(
        "Некоторые кошки пугливы"
    )

    assert result["source"] == "кошки"
    assert result["target"] == "пугливы"
    assert result["quantifier"] == "some"

    print("✅ Тест 2 пройден")


    result = parser.parse(
        "Ни один кит не рыба"
    )

    assert result["source"] == "кит"
    assert result["target"] == "рыба"
    assert result["relation"] == "NOT_IS"
    assert result["quantifier"] == "no"

    print("✅ Тест 3 пройден")


    result = parser.parse(
        "Все кошки являются животными"
    )

    assert result["source"] == "кошки"
    assert result["target"] == "животными"
    assert result["relation"] == "IS_A"

    print("✅ Тест 4 пройден")


    result = parser.parse(
        "Сократ — человек"
    )

    assert result["source"] == "сократ"
    assert result["target"] == "человек"

    print("✅ Тест 5 пройден")


    result = parser.parse(
        "Некоторые люди не смертны"
    )

    assert result["relation"] == "NOT_IS"
    assert result["quantifier"] == "some"

    print("✅ Тест 6 пройден")


    print("\n🔥 LogicParser v2.0 успешно прошёл все тесты.")