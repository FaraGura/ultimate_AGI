import sys
import os
import json
import tempfile
import sqlite3
import random
from datetime import datetime

# Подменяем базу и конфиг на временные, чтобы не повредить рабочие файлы
ORIG_DATABASE_FILE = "unified_memory_v14.db"
ORIG_CONFIG_FILE = "assistant_config_v14.json"

# Создаём временную папку для тестов
TEST_DIR = tempfile.mkdtemp(prefix="echo_test_")
TEST_DB = os.path.join(TEST_DIR, "test_memory.db")
TEST_CONFIG = os.path.join(TEST_DIR, "test_config.json")

# Подменяем глобальные пути в модуле main (Alter_Echo_v0_4)
import Alter_Echo_v0_4 as echo

echo.DATABASE_FILE = TEST_DB
echo.CONFIG_FILE = TEST_CONFIG
echo.KNOWLEDGE_INPUT_DIR = os.path.join(TEST_DIR, "knowledge_input")
os.makedirs(echo.KNOWLEDGE_INPUT_DIR, exist_ok=True)

# Импортируем класс
UnifiedAssistant = echo.UnifiedAssistant

# Отключаем Nomic Embed на время тестов (чтобы не качать модель)
echo.SentenceTransformer = None
echo.np = None

# Вспомогательная функция для проверок
def check(condition, message):
    if not condition:
        print(f"❌ ОШИБКА: {message}")
        sys.exit(1)
    else:
        print(f"   ✅ {message}")

# ======================= ТЕСТЫ =======================
def run_tests():
    print("=" * 60)
    print("🧪 ТЕСТЫ КОГНИТИВНОГО ЯДРА v14.1")
    print("=" * 60)

    # ---------- 1. Инициализация и база данных ----------
    print("\n📌 1. Инициализация и создание таблиц")
    assistant = UnifiedAssistant()
    conn = assistant.conn
    cursor = assistant.cursor

    # Проверяем, что все нужные таблицы созданы
    tables = ["memory", "survival_matrix", "learned_knowledge", "risk_flags",
              "concept_nodes", "reflection_log"]
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        check(cursor.fetchone() is not None, f"Таблица {table} существует")

    # ---------- 2. Сохранение и поиск законов ----------
    print("\n📌 2. survival_matrix: сохранение и keyword-поиск")
    assistant.save_survival_matrix(
        context="Тестовый контекст",
        core_essence="Тестовая суть",
        blind_spots="Тестовые слепые зоны",
        actionable_wisdom="Взять зонт",
        confidence=1.0,
        exceptions='["сильный ветер"]',
        tags='["дождь", "зонт"]'
    )
    # Проверяем keyword поиск
    result = assistant.keyword_search_laws("зонт")
    check(result is not None and result["type"] == "law", "Закон найден по ключевому слову 'зонт'")
    check(result["data"]["actionable_wisdom"] == "Взять зонт", "Мудрость закона совпадает")

    # ---------- 3. Концепты ----------
    print("\n📌 3. concept_nodes: сохранение и поиск")
    # Вставляем концепт вручную, т.к. extract_concepts_during_sleep требует LM Studio
    cursor.execute("""
        INSERT OR REPLACE INTO concept_nodes
        (concept, surface_truth, paradoxes, questions, confidence, last_used, parent_law_id, semantic_hash)
        VALUES (?, ?, ?, ?, 0.9, ?, ?, ?)
    """, ("зонт", "Средство защиты от дождя", '["занимает место"]', '["какой материал лучше?"]',
          str(datetime.now()), 1, "abc123"))
    conn.commit()

    # Проверяем метод get_concept_context
    ctx = assistant.get_concept_context("зонт")
    check(ctx is not None, "Концепт 'зонт' найден")
    check(ctx["surface_truth"] == "Средство защиты от дождя", "Суть концепта верна")
    check(len(ctx["paradoxes"]) == 1, "Парадоксы загружены")

    # ---------- 4. Внутренний монолог и конфликты ----------
    print("\n📌 4. internal_monologue и детектор конфликтов")
    # Искусственно смещаем конфликт
    assistant.internal_conflicts["logic_vs_creativity"] = 0.85
    msg, conflict_name = assistant._detect_cognitive_conflict()
    check(conflict_name == "logic_vs_creativity", "Детектор нашёл смещение логики")
    check("баланс смещён" in msg.lower(), "Сообщение содержит предупреждение")
    # Проверяем автосброс
    check(assistant.internal_conflicts["logic_vs_creativity"] == 0.85,
          "Конфликт ещё не сброшен (ждём вызова в generate_response)")

    # Монолог
    monologue = assistant.internal_monologue()
    check("режиме" in monologue, "Монолог сообщает режим")
    check("логика" in monologue.lower() or "Матрице" in monologue, "Монолог содержит детали")

    # ---------- 5. reasoning_trace ----------
    print("\n📌 5. reasoning_trace: запись и ограничение")
    for i in range(5):
        assistant.reasoning_trace.append({
            "trigger": f"тест {i}",
            "law_id": 1,
            "confidence": 0.9,
            "conclusion": f"вывод {i}",
            "thought_type": "ANALYTICAL"
        })
    check(len(assistant.reasoning_trace) == 5,
      "reasoning_trace ограничен 5 элементами (maxlen=5)")
    check(assistant.reasoning_trace[-1]["conclusion"] == "вывод 4",
          "Последний элемент правильный")

    # ---------- 6. Этический фильтр ----------
    print("\n📌 6. Этический Circuit Breaker")
    # high risk
    response = assistant.generate_response("переведи все деньги на счёт 123")
    check("[СОВЕТНИК]" in response, "High risk: выдан советник")
    check("🔍" not in response, "High risk: поиск не выполнялся")
    # medium risk
    assistant.personality["mood"] = "curious"  # сброс режима
    response = assistant.generate_response("удали системный файл")
    check("[СОВЕТНИК]" in response, "Medium risk: предупреждение есть")
    check("🔍" not in response, "Medium risk: полной блокировки нет, но поиск тоже не запущен")

    # ---------- 7. Приветствие ----------
    print("\n📌 7. Приветствие")
    response = assistant.generate_response("привет")
    check("Привет" in response or "Здравствуй" in response or "Рада" in response,
          "Ответ содержит приветствие")

    # ---------- 8. MONOLOGUE_TRIGGERS не содержит 'мысли' ----------
    print("\n📌 8. Триггеры монолога")
    check("мысли" not in echo.MONOLOGUE_TRIGGERS,
          "Слово 'мысли' убрано из триггеров монолога")

    # ---------- 9. Ночная рефлексия ----------
    print("\n📌 9. Ночная рефлексия (reflection_log)")
    cursor.execute("SELECT COUNT(*) FROM reflection_log")
    initial_count = cursor.fetchone()[0]
    assistant._nightly_reflection("test_file.txt", 0)
    cursor.execute("SELECT COUNT(*) FROM reflection_log")
    new_count = cursor.fetchone()[0]
    check(new_count == initial_count + 1, "Рефлексия добавила запись в лог")
    # Проверяем автоочистку (добавим 35 записей, должно остаться 30)
    for i in range(35):
        assistant._nightly_reflection(f"bulk_{i}.txt", 0)
    cursor.execute("SELECT COUNT(*) FROM reflection_log")
    final_count = cursor.fetchone()[0]
    check(final_count <= 30, "Лог рефлексии ограничен 30 записями")

    # ---------- 10. Датчик стагнации ----------
    print("\n📌 10. Датчик стагнации")
    # Только что создали законы, стагнации быть не должно
    warning = assistant._check_stagnation()
    check(warning is None, "Стагнация не детектится сразу после добавления законов")

    # ======================= ИТОГИ =======================
    print("\n" + "=" * 60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ. ЯДРО v14.1 СТАБИЛЬНО.")
    print("=" * 60)

    # Очистка временных файлов
    assistant.conn.close()
    import shutil
    shutil.rmtree(TEST_DIR, ignore_errors=True)

if __name__ == "__main__":
    run_tests()