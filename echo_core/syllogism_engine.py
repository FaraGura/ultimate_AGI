# echo_core/syllogism_engine.py
"""
Syllogism Engine v2.2 — дедуктивные умозаключения (силлогизмы).
Реализует 4 фигуры, 19 правильных модусов, правила терминов.
Без LLM, чистая детерминированная логика.
v2.2: Добавлена поддержка отрицаний (NOT_HAS, NOT_IS).
      Исправлен regex для захвата полной фразы после "не".
"""

import re
import logging
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger("SyllogismEngine")

VALID_MODES = {
    1: ["AAA", "EAE", "AII", "EIO"],
    2: ["AEE", "EAE", "AOO", "EIO"],
    3: ["AII", "IAI", "EIO", "OAO"],
    4: ["AII", "AEE", "IAI", "EIO", "EAO"],
}

# ---------------------------------------------------------------------------
# Жёсткая инициализация лемматизатора
# ---------------------------------------------------------------------------
try:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()
    _lemmatizer_available = True
    print("[ЛЕММАТИЗАЦИЯ] pymorphy3 успешно загружен, лемматизация активна")
except Exception as e:
    raise RuntimeError(
        "pymorphy3 недоступен. Лемматизация обязательна для работы силлогизмов. "
        "Установите: pip install pymorphy3 pymorphy3-dicts-ru"
    ) from e


def _canonical(word: str) -> str:
    """Каноническая форма слова: лемма через pymorphy3."""
    if not word:
        return word
    w = word.strip().lower().replace('ё', 'е')
    if not w:
        return w
    return _morph.parse(w)[0].normal_form


class SyllogismEngine:

    def __init__(self, db=None):
        self.db = db
        try:
            from language.logic_parser import LogicParser
            self.logic_parser = LogicParser()
        except ImportError:
            self.logic_parser = None

    @staticmethod
    def _strip_lead_conjunction(part: str) -> str:
        return re.sub(r'^\s*(?:а|и|но|значит|следовательно)\s*,?\s*', '', part.strip())

    def _validate_part(self, part: str) -> Optional[dict]:
        # 1. Отрицательные конструкции — приоритет
        #    "ни один X не Y Z..." (захватываем всю фразу после "не")
        m = re.match(
            r'ни\s+один\s+([а-яё]+)\s+не\s+(.+)',
            part, re.IGNORECASE
        )
        if m:
            return {
                'source': m.group(1), 'target': m.group(2).strip(),
                'relation': 'NOT_HAS', 'quantifier': 'no', 'confidence': 1.0,
            }
        #    "X не является Y"
        m = re.match(
            r'([а-яё]+)\s+не\s+является\s+(.+)',
            part, re.IGNORECASE
        )
        if m:
            return {
                'source': m.group(1), 'target': m.group(2).strip(),
                'relation': 'NOT_IS', 'quantifier': 'no', 'confidence': 0.9,
            }

        # 2. Утвердительные HAS
        m = re.match(
            r'у\s+(?:всех|каждого|любого)\s+([а-яё]+)\s+(?:есть|имеются)\s+(.+)',
            part, re.IGNORECASE
        )
        if not m:
            m = re.match(
                r'все\s+([а-яё]+)\s+(?:имеют|есть)\s+(.+)',
                part, re.IGNORECASE
            )
        if m:
            return {
                'source': m.group(1), 'target': m.group(2).strip(),
                'relation': 'HAS', 'quantifier': 'all', 'confidence': 1.0,
            }
        # 3. Утвердительные IS_A
        m = re.match(
            r'([а-яё]+)\s*[-–—]?\s*это\s+(.+)',
            part, re.IGNORECASE
        )
        if not m:
            m = re.match(
                r'([а-яё]+)\s+является\s+(.+)',
                part, re.IGNORECASE
            )
        if not m:
            m = re.match(
                r'([а-яё]+)\s*[-–—]\s*(.+)',
                part
            )
        if m:
            return {
                'source': m.group(1), 'target': m.group(2).strip(),
                'relation': 'IS_A', 'quantifier': 'all', 'confidence': 0.9,
            }
        # 4. Утвердительные свойства (все X Y)
        m = re.match(
            r'все\s+([а-яё]+)\s+(.+)',
            part, re.IGNORECASE
        )
        if m:
            return {
                'source': m.group(1), 'target': m.group(2).strip(),
                'relation': 'HAS_PROPERTY', 'quantifier': 'all', 'confidence': 0.9,
            }
        # 5. LogicParser
        if self.logic_parser:
            parsed = self.logic_parser.parse(part)
            if parsed:
                return parsed
        return None

    def _split_premises(self, text: str) -> Optional[List[dict]]:
        raw_parts = re.split(r'[,;]|(?<!\s)[-–—](?!\s)|(?<=\))\s*(?:а|и|но|значит)\s+', text)
        parsed = []
        for p in raw_parts:
            clean = self._strip_lead_conjunction(p)
            if not clean:
                continue
            fact = self._validate_part(clean)
            if fact:
                fact['source_orig'] = fact['source']
                fact['target_orig'] = fact['target']
                fact['source'] = _canonical(fact['source'])
                # Для составных предикатов лемматизируем только первое слово
                target = fact['target']
                if ' ' in target:
                    first_word = target.split()[0]
                    rest = target.split()[1:]
                    fact['target'] = _canonical(first_word) + ' ' + ' '.join(rest)
                else:
                    fact['target'] = _canonical(target)
                parsed.append(fact)
                if len(parsed) >= 2:
                    break
        if len(parsed) < 2:
            return None
        return parsed[:2]

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
        premises = self._split_premises(text)
        if not premises:
            return None
        conclusion = self.deduce(premises[0], premises[1])
        if not conclusion:
            return None

        subj = premises[1].get('source_orig', conclusion.get("source", ""))
        pred = premises[0].get('target_orig', conclusion.get("target", ""))
        quant = conclusion.get("quantifier", "")
        relation = premises[0].get('relation', 'IS_A')

        # --- Лингвистический анализ предиката ---
        first_word = pred.split()[0] if pred else ""
        is_property = False
        is_verb = False

        if first_word:
            try:
                parsed_pred = _morph.parse(first_word)[0]
                parsed_subj = _morph.parse(subj)[0]

                if any(t in parsed_pred.tag for t in ('ADJF', 'ADJS', 'PRTF', 'PRTS')):
                    is_property = True
                elif any(t in parsed_pred.tag for t in ('VERB', 'INFN')):
                    is_verb = True

                if is_property:
                    gender = parsed_subj.tag.gender
                    number = parsed_subj.tag.number
                    grammemes = set()
                    if number == 'sing':
                        grammemes.add('sing')
                        if gender:
                            grammemes.add(gender)
                    else:
                        grammemes.add('plur')
                    inflected = parsed_pred.inflect(grammemes)
                    if inflected:
                        rest = pred.split()[1:]
                        pred = " ".join([inflected.word] + rest)

                if is_verb and len(pred.split()) > 1:
                    subj_number = parsed_subj.tag.number
                    if subj_number == 'sing':
                        grammemes = {'sing', '3per'}
                        inflected = parsed_pred.inflect(grammemes)
                        if inflected:
                            rest = pred.split()[1:]
                            pred = " ".join([inflected.word] + rest)
            except Exception as e:
                logger.error(f"Ошибка согласования: {e}")

        # --- Сборка финального ответа ---
        if quant == "no":
            if relation == 'NOT_HAS':
                return f"{subj.capitalize()} не имеет {pred}"
            elif relation == 'NOT_IS':
                if is_verb:
                    return f"{subj.capitalize()} не {pred}"
                elif is_property:
                    return f"{subj.capitalize()} не является {pred}"
                else:
                    return f"{subj.capitalize()} не является {pred}"
            else:
                return f"{subj.capitalize()} не {pred}"
        elif quant == "all":
            if is_property or is_verb:
                return f"{subj.capitalize()} {pred}"
            else:
                return f"{subj.capitalize()} имеет {pred}"
        elif quant == "some":
            if is_property or is_verb:
                return f"Некоторые {subj} {pred}"
            else:
                return f"Некоторые {subj} имеют {pred}"
        else:
            return f"{subj.capitalize()} — {pred}"

    def extract_facts(self, text: str) -> List[Dict[str, str]]:
        facts = []
        parts = re.split(r'[,;]|(?<!\s)[-–—](?!\s)|(?<=\))\s*(?:а|и|но|значит)\s+', text)
        for part in parts:
            clean = self._strip_lead_conjunction(part)
            if not clean:
                continue
            fact = self._validate_part(clean)
            if not fact:
                continue
            pred = fact.get('relation')
            if pred in ('HAS', 'HAS_PROPERTY'):
                facts.append({
                    'predicate': 'has',
                    'arg1': _canonical(fact['source']),
                    'arg2': _canonical(fact['target'].split()[0]) if ' ' in fact['target'] else _canonical(fact['target']),
                })
            elif pred == 'IS_A':
                facts.append({
                    'predicate': 'is_a',
                    'arg1': _canonical(fact['source']),
                    'arg2': _canonical(fact['target']),
                })
            elif pred == 'NOT_HAS':
                facts.append({
                    'predicate': 'not_has',
                    'arg1': _canonical(fact['source']),
                    'arg2': _canonical(fact['target'].split()[0]) if ' ' in fact['target'] else _canonical(fact['target']),
                })
            elif pred == 'NOT_IS':
                facts.append({
                    'predicate': 'not_is',
                    'arg1': _canonical(fact['source']),
                    'arg2': _canonical(fact['target']),
                })
        return facts

    def _find_middle_term(self, p1: dict, p2: dict) -> Optional[str]:
        t1 = {_canonical(str(p1.get("source", ""))): p1.get("source"),
              _canonical(str(p1.get("target", ""))): p1.get("target")}
        t2 = {_canonical(str(p2.get("source", ""))): p2.get("source"),
              _canonical(str(p2.get("target", ""))): p2.get("target")}
        common = set(t1.keys()) & set(t2.keys())
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
        table = {"all": "A", "no": "E", "some": "I", "some_not": "O"}
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
        terms = {p1.get("source"), p1.get("target"), p2.get("source"), p2.get("target")}
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
        quantifier = {"A": "all", "E": "no", "I": "some", "O": "some_not"}.get(conclusion_letter)
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