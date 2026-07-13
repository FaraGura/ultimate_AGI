"""Build combined core_axioms.json from cognitive + physics sources."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "core_axioms.json")
COGNITIVE_PATH = os.path.join(
    os.path.dirname(ROOT),
    "UnifiedCoreV11 — копия",
    "data",
    "core_axioms.json",
)
PHYSICS_PATH = os.path.join(os.path.dirname(ROOT), "core_axioms.json")


def load_physics_axioms(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    # Strip optional markdown wrapper
    match = re.search(r"\{\s*\"description\"", raw, re.DOTALL)
    if match:
        raw = raw[match.start():]
    data = json.loads(raw)
    return data.get("axioms", [])


def physics_to_nodes_edges(axioms: list) -> tuple:
    nodes = [
        {
            "id": "physics_axioms_group",
            "type": "group",
            "payload": {"description": "Commonsense physics axioms"},
        }
    ]
    edges = []
    seen_concepts = set()

    for ax in axioms:
        ax_id = ax["id"]
        nodes.append({
            "id": ax_id,
            "type": "axiom",
            "payload": {
                "category": ax.get("category", "physics"),
                "axiom": ax.get("axiom", ""),
                "concepts": ax.get("concepts", []),
            },
        })
        edges.append({
            "source": "physics_axioms_group",
            "target": ax_id,
            "relation": "contains_axiom",
        })

        concepts = ax.get("concepts", [])
        for concept in concepts:
            if concept not in seen_concepts:
                seen_concepts.add(concept)
                nodes.append({"id": concept, "type": "concept"})
            edges.append({
                "source": ax_id,
                "target": concept,
                "relation": "involves",
            })
        for i in range(len(concepts) - 1):
            edges.append({
                "source": concepts[i],
                "target": concepts[i + 1],
                "relation": "causal",
            })

    return nodes, edges


def main():
    with open(COGNITIVE_PATH, "r", encoding="utf-8") as f:
        cognitive = json.load(f)

    physics_axioms = load_physics_axioms(PHYSICS_PATH)
    phys_nodes, phys_edges = physics_to_nodes_edges(physics_axioms)

    combined = {
        "description": "Combined core axioms: cognitive + physics commonsense",
        "version": "2.0",
        "provenance_source": "tabula_rasa_core",
        "nodes": cognitive.get("nodes", []) + phys_nodes,
        "edges": cognitive.get("edges", []) + phys_edges,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH}: {len(combined['nodes'])} nodes, {len(combined['edges'])} edges")


if __name__ == "__main__":
    main()
