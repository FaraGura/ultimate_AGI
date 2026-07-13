"""Consolidation / sleep engine — cluster episodes and strengthen causal edges."""

from collections import defaultdict
from typing import Dict, List, Set


class ConsolidationEngine:
    def __init__(self, causal_graph):
        self.causal_graph = causal_graph

    def run(self, episodes: List[Dict]) -> int:
        """
        Cluster episodes by shared concepts, strengthen or create enables edges.
        Returns the number of clusters formed.
        """
        if not episodes:
            return 0

        clusters = self._cluster_episodes(episodes)
        for _cluster_id, cluster_eps in clusters.items():
            shared = self._shared_concepts(cluster_eps)
            for concept in shared:
                for ep in cluster_eps:
                    target = ep.get("target") or ep.get("action")
                    if not target:
                        continue
                    existing = self.causal_graph.get_edges(
                        source=concept, target=target, relation="enables"
                    )
                    if existing:
                        self.causal_graph.update_confidence(
                            concept, target, "enables", 0.1
                        )
                    else:
                        self.causal_graph.add_edge(
                            concept, target, "enables", 0.5
                        )

        return len(clusters)

    def _cluster_episodes(self, episodes: List[Dict]) -> Dict[int, List[Dict]]:
        """Greedy clustering: episodes sharing at least one concept join a cluster."""
        clusters: Dict[int, List[Dict]] = {}
        concept_to_cluster: Dict[str, int] = {}
        next_id = 0

        for ep in episodes:
            concepts = set(ep.get("concepts") or [])
            matched_ids = {
                concept_to_cluster[c]
                for c in concepts
                if c in concept_to_cluster
            }

            if not matched_ids:
                cid = next_id
                next_id += 1
                clusters[cid] = [ep]
                for c in concepts:
                    concept_to_cluster[c] = cid
            else:
                primary = min(matched_ids)
                clusters.setdefault(primary, []).append(ep)
                for c in concepts:
                    concept_to_cluster[c] = primary
                for other_id in matched_ids:
                    if other_id != primary and other_id in clusters:
                        for merged_ep in clusters.pop(other_id):
                            clusters[primary].append(merged_ep)
                        for c, cid in list(concept_to_cluster.items()):
                            if cid == other_id:
                                concept_to_cluster[c] = primary

        return {k: v for k, v in clusters.items() if v}

    def _shared_concepts(self, episodes: List[Dict]) -> Set[str]:
        if not episodes:
            return set()
        counts: Dict[str, int] = defaultdict(int)
        for ep in episodes:
            for c in ep.get("concepts") or []:
                counts[c] += 1
        threshold = max(1, len(episodes) // 2)
        return {c for c, n in counts.items() if n >= threshold}