# migrate_schema.py
"""
Миграция схемы БД для Echo v16.1 (Forked Cognitive Architecture).
Добавляет поля контекстной истины, provenance, HLC, Language Kernel.
Безопасен: не удаляет данные, только ALTER TABLE ADD COLUMN.
"""
import sqlite3
import sys

DB_PATH = "unified_memory_v14.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Включаем WAL для надёжности
    cursor.execute("PRAGMA journal_mode=WAL")

    # --- Расширение concept_nodes ---
    concept_new_fields = [
        ("context_flags", "INTEGER DEFAULT 1"),
        ("provenance_source", "TEXT DEFAULT 'tabula_rasa'"),
        ("lamport_tick", "INTEGER DEFAULT 0"),
        ("physical_time", "INTEGER DEFAULT 0"),
        ("payload_cbor", "BLOB"),
        ("payload_schema_hash", "TEXT"),
        ("semantic_signature", "TEXT"),
        ("origin_instance_id", "TEXT"),
        ("parent_node_id", "TEXT"),
        ("created_by_module", "TEXT"),
        ("node_type", "TEXT"),  # 'axiom', 'symbol', 'action', 'state', 'logic', 'hypothesis', etc.
    ]
    for col_name, col_def in concept_new_fields:
        try:
            cursor.execute(f"ALTER TABLE concept_nodes ADD COLUMN {col_name} {col_def}")
            print(f"  concept_nodes.{col_name} — добавлено")
        except sqlite3.OperationalError:
            print(f"  concept_nodes.{col_name} — уже существует")

    # --- Расширение causal_edges ---
    edges_new_fields = [
        ("context_flags", "INTEGER DEFAULT 1"),
        ("provenance_source", "TEXT DEFAULT 'tabula_rasa'"),
        ("lamport_tick", "INTEGER DEFAULT 0"),
        ("physical_time", "INTEGER DEFAULT 0"),
        ("origin_instance_id", "TEXT"),
        ("parent_node_id", "TEXT"),
        ("created_by_module", "TEXT"),
    ]
    for col_name, col_def in edges_new_fields:
        try:
            cursor.execute(f"ALTER TABLE causal_edges ADD COLUMN {col_name} {col_def}")
            print(f"  causal_edges.{col_name} — добавлено")
        except sqlite3.OperationalError:
            print(f"  causal_edges.{col_name} — уже существует")

    # --- Создание таблицы graph_nodes (если не существует) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_nodes (
            node_id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            payload BLOB,
            context_flags INTEGER DEFAULT 1,
            provenance_source TEXT DEFAULT 'tabula_rasa',
            lamport_tick INTEGER DEFAULT 0,
            physical_time INTEGER DEFAULT 0,
            origin_instance_id TEXT,
            parent_node_id TEXT,
            created_by_module TEXT,
            payload_schema_hash TEXT,
            semantic_signature TEXT
        )
    """)
    print("  graph_nodes — таблица готова")

    # --- Создание таблицы graph_edges (если не существует) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_edges (
            edge_id TEXT PRIMARY KEY,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            context_flags INTEGER DEFAULT 1,
            provenance_source TEXT DEFAULT 'tabula_rasa',
            confidence_score REAL DEFAULT 1.0,
            lamport_tick INTEGER DEFAULT 0,
            physical_time INTEGER DEFAULT 0,
            origin_instance_id TEXT,
            parent_node_id TEXT,
            created_by_module TEXT,
            FOREIGN KEY (source_node_id) REFERENCES graph_nodes(node_id),
            FOREIGN KEY (target_node_id) REFERENCES graph_nodes(node_id)
        )
    """)
    print("  graph_edges — таблица готова")

    # --- Индексы для graph_edges ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_context ON graph_edges(context_flags)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_provenance ON graph_edges(provenance_source)")

    conn.commit()
    conn.close()
    print("\nМиграция завершена успешно.")

if __name__ == "__main__":
    migrate()