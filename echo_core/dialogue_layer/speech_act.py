# echo_core/dialogue_layer/speech_act.py
import re


class SpeechActClassifier:
    TEACHING_REGEX = re.compile(
        r"(тебя|тво[йёя]|тво[её]го|тобой|твоим|тебе)\s+(зовут|называют|именуют|величают|клич[уь]т|обозначают)",
        re.IGNORECASE
    )
    TEACHING_REGEX2 = re.compile(
        r"(тво[йёя]|тво[её]го|твоим)\s+(имя|название|прозвище|псевдоним|кличка|погоняло|марка|наименование)",
        re.IGNORECASE
    )
    QUESTION_SELF_REGEX = re.compile(
        r"(как|какое|какая|каков[ао]?)\s+(тебя|тво[йёя]|тво[её]го|тобой|твоим|тебе)\s*(зовут|называют|имя|название|звать|величать|клич[уь]т)?",
        re.IGNORECASE
    )
    QUESTION_SELF2_REGEX = re.compile(
        r"(кто|что)\s+ты",
        re.IGNORECASE
    )

    PRIORITIZED_PATTERNS = [
        ("CORRECTION", [
            "не так", "неправильно", "ошибка", "ты ошиблась", "это не так",
            "я ошибся", "я ошиблась",
        ]),
        ("REFLECTION", [
            "я думаю", "по-моему", "мне кажется", "моё мнение", "я считаю",
        ]),
        ("REQUEST", [
            "сделай", "расскажи", "объясни", "покажи", "напиши", "выполни",
        ]),
        ("GREETING", [
            "привет", "здравствуй", "добрый день",
            "добрый вечер", "доброе утро", "хай", "салют",
        ]),
    ]

    def classify(self, text: str) -> str:
        lower = text.lower().strip()

        # Приоритет 1: явные маркеры действий
        for act, patterns in self.PRIORITIZED_PATTERNS:
            words = set(re.findall(r'[а-яёa-z0-9]+', lower))
            for pat in patterns:
                if " " in pat:
                    if pat in lower:
                        return act
                else:
                    if pat in words:
                        return act

        # Приоритет 2: вопрос, если есть вопросительное слово или ?
        if self.QUESTION_SELF_REGEX.search(lower) or self.QUESTION_SELF2_REGEX.search(lower):
            return "QUESTION"
        if lower.endswith("?"):
            return "QUESTION"

        # Приоритет 3: TEACHING (утверждения о себе)
        if self.TEACHING_REGEX.search(lower) or self.TEACHING_REGEX2.search(lower):
            return "TEACHING"

        # CONFIRMATION / DENIAL для коротких фраз
        words = lower.split()
        if len(words) <= 2:
            if lower in ("да", "ага", "yes", "yep", "верно", "правильно", "именно",
                         "конечно", "естественно", "разумеется", "точно", "несомненно"):
                return "CONFIRMATION"
            if lower in ("нет", "no", "не", "отнюдь", "неверно", "неа"):
                return "DENIAL"

        return "UNKNOWN"


# ======================
if __name__ == "__main__":
    clf = SpeechActClassifier()
    assert clf.classify("Твоё имя Эхо") == "TEACHING"
    assert clf.classify("Тебя зовут Эхо") == "TEACHING"       # без ? — обучение
    assert clf.classify("Тебя зовут Эхо?") == "QUESTION"      # с ? — вопрос
    assert clf.classify("Как тебя зовут?") == "QUESTION"
    assert clf.classify("да") == "CONFIRMATION"
    assert clf.classify("конечно") == "CONFIRMATION"
    assert clf.classify("нет") == "DENIAL"
    print("✅ Все тесты SpeechActClassifier v2.1 пройдены.")