"""Регрессионный тест для проверки критических багов Echo."""

import sys
sys.path.insert(0, ".")

from echo_core.echo_core import EchoCore

print("=== Запуск регрессионного теста ===")

# Инициализация с debug-режимом
core = EchoCore(debug=True)

# Тест 1: Проверка, что DUL сбрасывается после обучения
print("\n--- Тест 1: Сброс DUL после обучения ---")
core.generate_response("Тебя зовут Эхо")   # TEACHING
core.generate_response("Да")               # CONFIRMATION
resp = core.generate_response("Что такое вода?")  # Должен быть обычный ответ, не про имя
assert "Меня зовут" not in resp, f"DUL не сбросился! Ответ: {resp}"
print("✅ Тест 1 пройден: DUL сброшен")

# Тест 2: Проверка, что Identity не перехватывает не-identity вопросы
print("\n--- Тест 2: Identity не захватывает чужие запросы ---")
resp = core.generate_response("Как дела?")
assert "Меня зовут" not in resp, f"Identity захватил запрос! Ответ: {resp}"
print("✅ Тест 2 пройден: Identity не отвечает на общие вопросы")

# Тест 3: TEACHING не перехватывает вопросы
print("\n--- Тест 3: TEACHING не перехватывает вопросы ---")
resp = core.generate_response("Как твоё имя?")
# Может ответить про имя, но не должен уходить в цикл обучения
assert "Правильно ли я поняла" not in resp, f"TEACHING перехватил вопрос! Ответ: {resp}"
print("✅ Тест 3 пройден: TEACHING не перехватывает вопросы")

# Тест 4: Стеммер работает
print("\n--- Тест 4: Стеммер распознаёт словоформы ---")
from utils.russian_stemmer import stem
assert stem("обновлю") == "обновл", f"Стеммер не сработал: {stem('обновлю')}"
assert stem("обновлять") == "обнов", f"Стеммер не сработал: {stem('обновлять')}"
assert stem("обновление") == "обновлен", f"Стеммер не сработал: {stem('обновление')}"
print("✅ Тест 4 пройден: стеммер работает")

print("\n=== ВСЕ ТЕСТЫ ПРОЙДЕНЫ ===")
core.episodic.stop()