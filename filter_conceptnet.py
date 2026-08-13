#UnifiedCoreV11\filter_conceptnet.py
import csv
import os
import re

INPUT_FILE = "assertions.csv"
OUTPUT_DIR = os.path.join("echo_core", "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "conceptnet_ru_filtered.csv")

CN_TO_ECHO = {
    "IsA": "IS_A",
    "PartOf": "HAS_PROPERTY",
    "HasA": "HAS_PROPERTY",
    "UsedFor": "CAN_DO",
    "CapableOf": "CAN_DO",
    "LocatedNear": "LOCATED_IN",
    "AtLocation": "LOCATED_IN",
    "Causes": "CAUSES",
}

def extract_russian_word(uri: str) -> str:
    """
    Извлекает русское слово из URI вида:
    /c/ru/слово/n/   или   /c/ru/слово/a/   или   /c/ru/слово/
    Также обрабатывает случаи со скобками и лишними пробелами.
    """
    # Убираем скобки и разбиваем по пробелам и слешам
    clean = uri.replace("[", "").replace("]", "").replace("/", " ").strip()
    parts = clean.split()
    
    # Ищем часть, которая начинается с "c" и содержит "ru"
    for i, part in enumerate(parts):
        if part == "c" and i + 1 < len(parts) and parts[i + 1] == "ru":
            # Слово находится через одну позицию после "ru"
            if i + 2 < len(parts):
                word = parts[i + 2]
                # Заменяем подчёркивания на пробелы
                word = word.replace("_", " ").strip()
                # Проверяем, что слово содержит кириллицу
                if re.search(r'[а-яёА-ЯЁ]', word) and len(word) >= 2:
                    return word
    return ""

def extract_relation(uri: str) -> str:
    """Извлекает тип отношения из URI вида /r/Antonym/."""
    clean = uri.replace("[", "").replace("]", "").strip("/")
    parts = clean.split("/")
    if len(parts) >= 3 and parts[0] == "r":
        return parts[1]
    return ""

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total = 0
    kept = 0
    with open(INPUT_FILE, "r", encoding="utf-8") as fin, \
         open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        for row in reader:
            total += 1
            if total % 1_000_000 == 0:
                print(f"Обработано {total} строк, отобрано {kept}...")
            try:
                if len(row) < 3:
                    continue
                
                # Очищаем строки от лишних пробелов
                full_row = " ".join(row).strip()
                # Разбиваем по пробелам, чтобы найти части URI
                tokens = full_row.split()
                
                # Ищем русские слова и отношение
                start_word = ""
                end_word = ""
                rel_type = ""
                
                for token in tokens:
                    token = token.strip()
                    if token.startswith("/c/ru/"):
                        # Извлекаем русское слово
                        word = token.split("/")[3] if len(token.split("/")) > 3 else ""
                        word = word.replace("_", " ").strip()
                        if re.search(r'[а-яёА-ЯЁ]', word) and len(word) >= 2:
                            if not start_word:
                                start_word = word
                            else:
                                end_word = word
                    elif token.startswith("/r/"):
                        rel_type = token.split("/")[2] if len(token.split("/")) > 2 else ""
                
                if not start_word or not end_word or not rel_type:
                    continue
                
                echo_rel = CN_TO_ECHO.get(rel_type, "RELATED_TO")
                writer.writerow([start_word, echo_rel, end_word])
                kept += 1
            except Exception:
                continue

    print(f"Готово. Всего строк: {total}, отобрано русских: {kept}")
    print(f"Результат сохранён в {OUTPUT_FILE}")

if __name__ == "__main__":
    main()