"""Стеммер для русского языка — отсечение окончаний и суффиксов."""

import re

NOUN_ENDINGS = [
    "ами", "ями", "ов", "ев", "ей", "ах", "ях", "ом", "ем", "ой", "ей",
    "ы", "и", "а", "я", "о", "е", "у", "ю", "ь",
]

ADJ_ENDINGS = [
    "ого", "его", "ому", "ему", "ыми", "ими", "ом", "ем", "ой", "ей",
    "ый", "ий", "ая", "яя", "ое", "ее", "ые", "ие",
]

VERB_ENDINGS = [
    "ешь", "ет", "ем", "ете", "ут", "ют", "ат", "ят",
    "ал", "ала", "али", "ил", "ила", "или",
    "ть", "ти", "чь",
    "л", "ла", "ло", "ли",
    "ся", "сь",
]

ALL_ENDINGS = sorted(
    set(NOUN_ENDINGS + ADJ_ENDINGS + VERB_ENDINGS),
    key=len,
    reverse=True
)


def normalize_hyphenated(word: str) -> str:
    if not word:
        return word
    return re.sub(r'[-\s]+', '', word)


def stem(word: str) -> str:
    word = normalize_hyphenated(word)
    word = word.lower().strip(".,!?():;\"'-")
    if len(word) < 3:
        return word

    for ending in ALL_ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:-len(ending)]

    return word