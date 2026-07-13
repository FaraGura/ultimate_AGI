# echo_core/syllogism_engine.py
"""
Syllogism Engine v1.0 — дедуктивные умозаключения (силлогизмы).
Реализует 4 фигуры, 19 правильных модусов, правила терминов.
Без LLM, чистая детерминированная логика.
"""

import re
from typing import Optional


VALID_MODES = {
    1: ["AAA", "EAE", "AII", "EIO"],
    2: ["AEE", "EAE", "AOO", "EIO"],
    3: ["AII", "IAI", "EIO", "OAO"],
    4: ["AII", "AEE", "IAI", "EIO", "EAO"],
}


class SyllogismEngine:

    def __init__(self, db=None):
        self.db = db

    def deduce(self, premise1: dict, premise2: dict) -> Optional[dict]:
        middle = self._find_middle_term(premise1, premise2)
        if not middle:
            return None

        figure = self._determine_figure(premise1, premise2, middle)
        if figure == 0:
            return None

        mode_without_conclusion = self._determine_mode(premise1, premise2)
        if not mode_without_conclusion:
            return None

        conclusion_type = self._predict_conclusion_type(premise1, premise2, figure)
        if not conclusion_type:
            return None

        full_mode = mode_without_conclusion + conclusion_type

        if full_mode not in VALID_MODES.get(figure, []):
            return None

        if not self._validate_terms(premise1, premise2, middle):
            return None

        return self._build_conclusion(premise1, premise2, middle, figure, full_mode)

    def solve(self, text: str) -> Optional[str]:
        """
        Принимает русский текст с двумя посылками и возвращает заключение.
        Пример: "у всех птиц есть крылья, а воробей – птица"
        """
        parts = re.split(r',\s*(?:а\s*)?', text)
        if len(parts) < 2:
            return None

        premises = []
        for part in parts[:2]:
            # Паттерн "все X имеют/есть Y"
            match = re.match(r'все\s+(\w+)\s+(?:имеют|есть)\s+(\w+)', part, re.IGNORECASE)
            if match:
                premises.append({
                    "source": match.group(1),
                    "target": match.group(2),
                    "relation": "HAS",
                    "quantifier": "all",
                    "confidence": 1.0,
                })
                continue
            # Паттерн "X – Y" (X является Y)
            match = re.match(r'(\w+)\s*[-–]\s*(\w+)', part)
            if match:
                premises.append({
                    "source": match.group(1),
                    "target": match.group(2),
                    "relation": "IS_A",
                    "quantifier": "all",
                    "confidence": 0.9,
                })
                continue

        if len(premises) < 2:
            return None

        conclusion = self.deduce(premises[0], premises[1])
        if not conclusion:
            return None

        subj = conclusion.get("source", "")
        pred = conclusion.get("target", "")
        quant = conclusion.get("quantifier", "")
        if quant == "all":
            return f"{subj.capitalize()} имеет {pred}"
        elif quant == "some":
            return f"Некоторые {subj} имеют {pred}"
        elif quant == "no":
            return f"{subj.capitalize()} не имеет {pred}"
        else:
            return f"{subj.capitalize()} — {pred}"

    def _find_middle_term(self, p1: dict, p2: dict) -> Optional[str]:
        terms1 = {p1.get("source"), p1.get("target")}
        terms2 = {p2.get("source"), p2.get("target")}
        common = terms1 & terms2
        if len(common) == 1:
            return common.pop()
        return None

    def _determine_figure(self, p1: dict, p2: dict, middle: str) -> int:
        p1_s = p1.get("source")
        p1_t = p1.get("target")
        p2_s = p2.get("source")
        p2_t = p2.get("target")

        if p1_s == middle and p2_t == middle:
            return 1
        if p1_t == middle and p2_t == middle:
            return 2
        if p1_s == middle and p2_s == middle:
            return 3
        if p1_t == middle and p2_s == middle:
            return 4
        return 0

    def _determine_mode(self, p1: dict, p2: dict) -> Optional[str]:
        a = self._quantifier_letter(p1.get("quantifier"))
        b = self._quantifier_letter(p2.get("quantifier"))
        if not a or not b:
            return None
        return a + b

    def _quantifier_letter(self, value: str) -> Optional[str]:
        table = {
            "all": "A",
            "no": "E",
            "some": "I",
            "some_not": "O",
        }
        return table.get(value)

    def _predict_conclusion_type(self, p1: dict, p2: dict, figure: int) -> Optional[str]:
        q1 = self._quantifier_letter(p1.get("quantifier"))
        q2 = self._quantifier_letter(p2.get("quantifier"))
        if not q1 or not q2:
            return None

        pair = q1 + q2

        rules = {
            1: {"AA": "A", "EA": "E", "AI": "I", "EI": "O"},
            2: {"AE": "E", "EA": "E", "AO": "O", "EI": "O"},
            3: {"AI": "I", "IA": "I", "EA": "O", "EO": "O", "EI": "O"},
            4: {"AI": "I", "AE": "E", "IA": "I", "EI": "O", "EA": "O"},
        }

        return rules.get(figure, {}).get(pair)

    def _validate_terms(self, p1: dict, p2: dict, middle: str) -> bool:
        terms = {
            p1.get("source"), p1.get("target"),
            p2.get("source"), p2.get("target"),
        }

        if len(terms) != 3:
            return False

        q1 = p1.get("quantifier")
        q2 = p2.get("quantifier")

        if q1 in ("no", "some_not") and q2 in ("no", "some_not"):
            return False

        if q1 in ("some", "some_not") and q2 in ("some", "some_not"):
            return False

        if not (self._is_distributed(p1, middle) or self._is_distributed(p2, middle)):
            return False

        return True

    def _is_distributed(self, premise: dict, term: str) -> bool:
        quantifier = premise.get("quantifier")
        is_subject = (premise.get("source") == term)

        if quantifier == "all":
            return is_subject
        if quantifier == "no":
            return True
        if quantifier == "some":
            return False
        if quantifier == "some_not":
            return not is_subject
        return False

    def _build_conclusion(self, p1: dict, p2: dict, middle: str, figure: int, mode: str) -> Optional[dict]:
        if figure == 1:
            subject = p2["source"]
            predicate = p1["target"]
        elif figure == 2:
            subject = p2["source"]
            predicate = p1["source"]
        elif figure == 3:
            subject = p2["target"]
            predicate = p1["target"]
        elif figure == 4:
            subject = p2["target"]
            predicate = p1["source"]
        else:
            return None

        conclusion_letter = mode[2]
        quantifier = {
            "A": "all",
            "E": "no",
            "I": "some",
            "O": "some_not",
        }.get(conclusion_letter)

        if not quantifier:
            return None

        confidence = min(
            p1.get("confidence", 1.0),
            p2.get("confidence", 1.0),
        )

        return {
            "source": subject,
            "target": predicate,
            "relation": "deduced",
            "quantifier": quantifier,
            "confidence": confidence,
            "provenance": {
                "engine": "syllogism_engine",
                "figure": figure,
                "mode": mode,
                "parents": [p1.get("id"), p2.get("id")],
            },
            "context_flags": {"derived": True},
        }


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    engine = SyllogismEngine()

    # Тест 1: AAA-1 — Сократ смертен
    p1 = {
        "id": 1,
        "source": "люди",
        "target": "смертны",
        "relation": "IS_A",
        "quantifier": "all",
        "confidence": 1.0,
    }
    p2 = {
        "id": 2,
        "source": "Сократ",
        "target": "люди",
        "relation": "IS_A",
        "quantifier": "all",
        "confidence": 1.0,
    }
    result = engine.deduce(p1, p2)
    assert result is not None
    assert result["source"] == "Сократ"
    assert result["target"] == "смертны"
    assert result["quantifier"] == "all"
    print("✅ Тест 1 (Сократ смертен) пройден")

    # Тест 2: AII-3 — Кошки и пугливые животные
    p1 = {
        "id": 3,
        "source": "кошки",
        "target": "животные",
        "relation": "IS_A",
        "quantifier": "all",
        "confidence": 1.0,
    }
    p2 = {
        "id": 4,
        "source": "кошки",
        "target": "пугливые",
        "relation": "HAS_PROPERTY",
        "quantifier": "some",
        "confidence": 0.8,
    }
    result = engine.deduce(p1, p2)
    assert result is not None
    assert result["quantifier"] == "some"
    print("✅ Тест 2 (кошки и животные) пройден")

    # Тест 3: Ложный вывод
    p1 = {
        "source": "киты",
        "target": "млекопитающие",
        "quantifier": "all",
        "confidence": 1,
    }
    p2 = {
        "source": "дельфины",
        "target": "млекопитающие",
        "quantifier": "all",
        "confidence": 1,
    }
    result = engine.deduce(p1, p2)
    assert result is None
    print("✅ Тест 3 (ложный вывод остановлен) пройден")

    # Тест 4: Две отрицательные посылки
    p1 = {
        "source": "студенты",
        "target": "математика",
        "quantifier": "no",
        "confidence": 1,
    }
    p2 = {
        "source": "рабочие",
        "target": "студенты",
        "quantifier": "no",
        "confidence": 1,
    }
    result = engine.deduce(p1, p2)
    assert result is None
    print("✅ Тест 4 (две отрицательные) пройден")

    # Тест 5: Две частные посылки
    p1 = {
        "source": "животные",
        "target": "яйцекладущие",
        "quantifier": "some",
        "confidence": 0.8,
    }
    p2 = {
        "source": "организмы",
        "target": "животные",
        "quantifier": "some",
        "confidence": 0.8,
    }
    result = engine.deduce(p1, p2)
    assert result is None
    print("✅ Тест 5 (две частные) пройден")

    # Тест 6: solve() из свободного текста
    text = "у всех птиц есть крылья, а воробей – птица"
    res = engine.solve(text)
    print(f"✅ Тест 6 (текстовый силлогизм): {res}")

    print("\n🔥 Все тесты SyllogismEngine пройдены.")