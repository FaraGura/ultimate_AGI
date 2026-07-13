# echo_core/dialogue_layer/self_resolver.py
"""
Self/Other Resolver v1.1
Определяет, о ком идёт речь в высказывании, с позиции Echo.
Возвращает: SELF, USER, THIRD_PERSON, OBJECT, UNKNOWN
"""
import re

class SelfResolver:
    # Местоимения первого лица (говорящий)
    SELF_PATTERNS = [
        r"\bя\b", r"\bменя\b", r"\bмне\b", r"\bмной\b",
        r"\bмо[йё]\b", r"\bмо[её]го\b", r"\bмы\b", r"\bнас\b",
    ]
    # Местоимения второго лица (слушатель)
    USER_PATTERNS = [
        r"\bты\b", r"\bтебя\b", r"\bтебе\b", r"\bтобой\b",
        r"\bтво[йё]\b", r"\bвы\b", r"\bвас\b",
    ]
    # Местоимения третьего лица
    THIRD_PERSON_PATTERNS = [
        r"\bон\b", r"\bона\b", r"\bоно\b", r"\bони\b",
        r"\bего\b", r"\bеё\b", r"\bему\b", r"\bей\b", r"\bим\b",
    ]

    def resolve(self, word: str) -> str:
        """Определяет грамматическое лицо для изолированного токена."""
        w = word.lower().strip()
        for pat in self.SELF_PATTERNS:
            if re.fullmatch(pat, w):
                return "1ST_PERSON"  # Говорящий
        for pat in self.USER_PATTERNS:
            if re.fullmatch(pat, w):
                return "2ND_PERSON"  # Слушатель
        for pat in self.THIRD_PERSON_PATTERNS:
            if re.fullmatch(pat, w):
                return "3RD_PERSON"  # Третье лицо
        return "OBJECT"

    def resolve_text(self, text: str) -> str:
        """
        Определяет прагматический фокус высказывания с позиции Echo.
        Если человек говорит "Ты..." — он говорит про Echo (SELF).
        Если человек говорит "Я..." — он говорит про себя (USER).
        """
        words = set(re.findall(r'[а-яёa-z0-9]+', text.lower()))
        
        has_1st = any(self.resolve(w) == "1ST_PERSON" for w in words)
        has_2nd = any(self.resolve(w) == "2ND_PERSON" for w in words)
        has_third = any(self.resolve(w) == "3RD_PERSON" for w in words)

        if has_2nd:
            return "SELF"
        if has_1st:
            return "USER"
        if has_third:
            return "THIRD_PERSON"
        return "OBJECT"


# ======================
# ОБНОВЛЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    res = SelfResolver()
    assert res.resolve("я") == "1ST_PERSON"
    assert res.resolve("тебя") == "2ND_PERSON"
    
    # Теперь роли разделены идеально:
    assert res.resolve_text("Меня зовут Сёма") == "USER"  # Человек говорит о себе
    assert res.resolve_text("Тебя зовут Echo") == "SELF"  # Человек говорит об Echo
    assert res.resolve_text("Echo — это система") == "OBJECT"
    
    print("✅ Все прагматические тесты SelfResolver пройдены.")