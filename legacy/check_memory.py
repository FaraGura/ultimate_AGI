import sqlite3
import os

DATABASE_FILE = "unified_memory_v11.db"


def check_laws():
    print("=" * 60)
    print(" ПРОВЕРКА БАЗЫ ЗНАНИЙ ЭХО ")
    print("=" * 60)

    if not os.path.exists(DATABASE_FILE):
        print(f"[Ошибка]: Файл '{DATABASE_FILE}' не найден. Сначала запустите Эхо.")
        return

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM logic_laws")
        law_count = cursor.fetchone()[0]
        print(f"\nЛогических законов: {law_count}")

        cursor.execute("SELECT id, premise, consequence, solution FROM logic_laws LIMIT 10")
        for row in cursor.fetchall():
            print(f"\nЗакон №{row[0]}:")
            print(f"  Условие: {row[1]}")
            print(f"  Следствие: {row[2]}")
            print(f"  Вывод: {row[3]}")

        cursor.execute("SELECT COUNT(*) FROM learned_knowledge")
        knowledge_count = cursor.fetchone()[0]
        print(f"\nИзвлечённых знаний: {knowledge_count}")

        cursor.execute(
            "SELECT knowledge_type, category, content FROM learned_knowledge ORDER BY id DESC LIMIT 10"
        )
        for ktype, category, content in cursor.fetchall():
            cat = category or "—"
            print(f"  [{ktype}/{cat}] {content[:100]}")

        cursor.execute("SELECT COUNT(*) FROM risk_flags")
        risk_count = cursor.fetchone()[0]
        print(f"\nПомеченных рисков: {risk_count}")

    except sqlite3.OperationalError as e:
        print(f"[Ошибка]: Таблица ещё не создана — запустите Эхо один раз. ({e})")
    finally:
        conn.close()


if __name__ == "__main__":
    check_laws()
    print("\nПроверка завершена.")
    input("Нажмите Enter для выхода...")
