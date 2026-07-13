# echo_core/graph_exporter.py
"""
Graph Exporter — утилита для отладки модели мира Echo.
Сохраняет CausalGraph (NetworkX) в JSON для визуализации.
"""

import json

def export_graph_to_json(causal_graph, filepath: str) -> None:
    """
    Экспортирует граф в JSON-формат.
    :param causal_graph: объект CausalGraph (с атрибутом ._load_nx() или готовым графом)
    :param filepath: путь к выходному файлу, например "data/model_snapshot.json"
    """
    # Пытаемся получить готовый граф NetworkX
    if hasattr(causal_graph, '_load_nx'):
        G = causal_graph._load_nx(min_confidence=0.0)  # Берём все связи
    else:
        G = causal_graph  # На случай, если передали сам граф

    data = {
        "nodes": [],
        "edges": []
    }

    # Добавляем узлы
    for node_id in G.nodes():
        data["nodes"].append({
            "id": node_id,
            "type": G.nodes[node_id].get("type", "unknown")
        })

    # Добавляем рёбра
    for source, target, edge_data in G.edges(data=True):
        data["edges"].append({
            "source": source,
            "target": target,
            "relation": edge_data.get("relation", "unknown"),
            "confidence": edge_data.get("confidence", 1.0)
        })

    # Запись в файл
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Граф экспортирован: {len(data['nodes'])} узлов, {len(data['edges'])} связей -> {filepath}")


# Простой тест (запускается, если выполнить этот файл напрямую)
if __name__ == "__main__":
    try:
        import networkx as nx
        # Создаём тестовый граф
        G = nx.DiGraph()
        G.add_node("сковородка", type="object")
        G.add_node("железо", type="material")
        G.add_edge("сковородка", "железо", relation="MADE_OF", confidence=0.9)

        # Экспортируем во временный файл
        export_graph_to_json(G, "test_graph.json")
        print("Тест пройден, проверь файл test_graph.json")
    except ImportError:
        print("NetworkX не установлен, тест невозможен")