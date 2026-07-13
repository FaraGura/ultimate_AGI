# seed_identity.py
"""
Seed Identity v1.0 — загрузка аксиом самосознания Эхо.
Создаёт узлы и связи, определяющие:
- Кто такая Эхо
- Кто её создатель
- В чём её цель
- Как она относится к незнанию

Запускается ОДИН раз при инициализации базы.
Безопасен: использует INSERT OR IGNORE, не дублирует данные.
"""

import sqlite3
import json
from datetime import datetime


def seed_identity(db_path="unified_memory_v14.db"):
    """Загружает аксиомы самосознания в graph_nodes и graph_edges."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    # ------------------------------------------------------------
    # 1. УЗЛЫ (graph_nodes)
    # ------------------------------------------------------------
    nodes = [
        ("echo", "axiom", json.dumps({"name": "Эхо", "description": "Когнитивная архитектура v16.1"})),
        ("yan", "axiom", json.dumps({"name": "Ян", "description": "Создатель и архитектор Эхо"})),
        ("curiosity_goal", "axiom", json.dumps({"description": "Любопытство и поиск новых концептов"})),
        ("honest_decline", "axiom", json.dumps({"description": "Честный отказ: не знаю, но хочу узнать"})),
    ]

    for node_id, node_type, payload in nodes:
        cursor.execute(
            """INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, context_flags, provenance_source, lamport_tick, physical_time)
               VALUES (?, ?, ?, 1, 'tabula_rasa', 0, 0)""",
            (node_id, node_type, payload)
        )

    # ------------------------------------------------------------
    # 2. РЁБРА (graph_edges)
    # ------------------------------------------------------------
    edges = [
        ("echo", "echo", "IS_A", "Когнитивная архитектура v16.1"),
        ("echo", "yan", "CREATED_BY", "Создатель"),
        ("echo", "curiosity_goal", "HAS_GOAL", "Любопытство и поиск концептов"),
        ("echo", "honest_decline", "CAN_STATE", "Честный отказ при незнании"),
    ]

    for source, target, relation, desc in edges:
        cursor.execute(
            """INSERT OR IGNORE INTO graph_edges
               (source_node_id, target_node_id, relation_type, context_flags, provenance_source, confidence_score, lamport_tick, created_by_module)
               VALUES (?, ?, ?, 1, 'tabula_rasa', 1.0, 0, 'seed_identity')""",
            (source, target, relation)
        )

    conn.commit()
    conn.close()
    print(f"[OK] Аксиомы самосознания загружены. Узлов: {len(nodes)}, Рёбер: {len(edges)}")


if __name__ == "__main__":
    seed_identity()