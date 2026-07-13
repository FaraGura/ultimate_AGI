# language/pos_tagger.py
"""
POS Tagger v1.0 — минимальный rule-based теггер частей речи.
Различает служебные слова (союзы, предлоги) и смысловые единицы (существительные, глаголы).
Не создаёт узлы для служебных слов. Возвращает токены с метками.
Без LLM, на основе словарей и позиционных правил.
"""

from typing import List, Dict, Optional


class POSTagger:
    # Закрытые списки служебных слов
    PREPOSITIONS = {"в", "на", "с", "под", "над", "к", "по", "из", "от", "до", "без", "для", "через", "перед"}
    CONJUNCTIONS = {"и", "или", "либо", "но", "а", "если", "то", "потому", "что", "когда", "тогда", "также", "тоже"}
    PARTICLES = {"не", "ни", "бы", "же", "ли", "даже", "только", "лишь", "вот", "вон"}

    def tag(self, words: List[str]) -> List[Dict[str, str]]:
        """
        Принимает список слов, возвращает список токенов с метками:
        - 'function' — служебное слово (предлог, союз, частица)
        - 'content'  — знаменательное слово (существительное, глагол, прилагательное)
        - 'unknown'  — не удалось определить
        """
        tokens = []
        for i, word in enumerate(words):
            token = {"word": word, "index": i}
            lower = word.lower().strip(".,!?():;\"'-")

            if lower in self.PREPOSITIONS or lower in self.CONJUNCTIONS or lower in self.PARTICLES:
                token["pos"] = "function"
                token["type"] = self._detect_function_type(lower)
            elif len(lower) <= 2 and lower.isalpha():
                # Очень короткие слова — скорее всего, служебные
                token["pos"] = "function"
                token["type"] = "unknown_short"
            else:
                token["pos"] = "content"
                token["type"] = self._guess_content_type(lower, i, words)

            tokens.append(token)

        return tokens

    def _detect_function_type(self, word: str) -> str:
        if word in self.PREPOSITIONS:
            return "preposition"
        if word in self.CONJUNCTIONS:
            return "conjunction"
        if word in self.PARTICLES:
            return "particle"
        return "unknown_function"

    def _guess_content_type(self, word: str, index: int, words: List[str]) -> str:
        """
        Простейшая эвристика для определения типа знаменательного слова.
        Не претендует на точность, но даёт первичную разметку.
        """
        # Если слово заканчивается на -ть, -ти — возможно, глагол
        if word.endswith(("ть", "ти", "чь", "ать", "ять", "еть", "ить", "оть", "уть")):
            return "verb"
        # Если слово заканчивается на -ый, -ий, -ой — возможно, прилагательное
        if word.endswith(("ый", "ий", "ой", "ая", "яя", "ое", "ее")):
            return "adjective"
        # Если перед словом был предлог — возможно, существительное
        if index > 0 and words[index - 1].lower() in self.PREPOSITIONS:
            return "noun"
        return "content"

    def get_content_words(self, words: List[str]) -> List[str]:
        """Возвращает только смысловые слова (content), отбрасывая служебные."""
        tokens = self.tag(words)
        return [t["word"] for t in tokens if t.get("pos") == "content"]

    def get_function_words(self, words: List[str]) -> List[str]:
        """Возвращает только служебные слова (function)."""
        tokens = self.tag(words)
        return [t["word"] for t in tokens if t.get("pos") == "function"]

    def extract_operators(self, words: List[str]) -> Dict[str, List[int]]:
        """
        Извлекает логические операторы (AND, OR, OPPOSITION) из списка слов.
        Возвращает словарь с индексами операторов.
        """
        tokens = self.tag(words)
        operators = {"AND": [], "OR": [], "OPPOSITION": [], "IF": [], "THEN": []}

        for t in tokens:
            if t.get("pos") != "function":
                continue
            word = t["word"].lower().strip(".,!?():;\"'-")
            if word == "и":
                operators["AND"].append(t["index"])
            elif word in ("или", "либо"):
                operators["OR"].append(t["index"])
            elif word in ("а", "но"):
                operators["OPPOSITION"].append(t["index"])
            elif word == "если":
                operators["IF"].append(t["index"])
            elif word == "то":
                operators["THEN"].append(t["index"])

        return operators


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    tagger = POSTagger()

    # Тест 1: Различение служебных и смысловых слов
    words = ["я", "иду", "в", "школу"]
    tokens = tagger.tag(words)
    assert tokens[0]["pos"] == "content"   # я
    assert tokens[1]["pos"] == "content"   # иду
    assert tokens[2]["pos"] == "function"  # в
    assert tokens[3]["pos"] == "content"   # школу
    print("✅ Тест 1 (базовое тегирование) пройден")

    # Тест 2: Фильтрация служебных слов
    content = tagger.get_content_words(["в", "доме", "и", "на", "улице"])
    assert content == ["доме", "улице"]
    print("✅ Тест 2 (фильтрация служебных) пройден")

    # Тест 3: Извлечение операторов
    ops = tagger.extract_operators(["я", "и", "он", "или", "она", "а", "не", "знаю"])
    assert 1 in ops["AND"]       # "и"
    assert 3 in ops["OR"]        # "или"
    assert 5 in ops["OPPOSITION"] # "а"
    print("✅ Тест 3 (операторы) пройден")

    # Тест 4: Очень короткие слова — функция
    tokens = tagger.tag(["а", "я", "в", "б"])
    assert tokens[0]["pos"] == "function"  # а
    assert tokens[1]["pos"] == "content"   # я (хоть и короткое, но знаменательное)
    assert tokens[2]["pos"] == "function"  # в
    # "б" — короткое, но частица или неполное слово; теггер помечает как function
    assert tokens[3]["pos"] == "function"
    print("✅ Тест 4 (короткие слова) пройден")

    print("\n🔥 Все тесты POSTagger пройдены.")