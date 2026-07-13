# echo_core/concept_formation.py
"""
Concept Formation v1.0 — автоматическое рождение новых понятий.
Анализирует CausalGraph, находит кластеры связанных узлов и создаёт гипотезы
о новых, более общих концептах (например, яблоко + банан → фрукт).
"""
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from utils.utils_logger import get_logger


class ConceptFormation:
    def __init__(self, causal_graph, knowledge_revision_engine=None):
        self.causal = causal_graph
        self.knowledge_revision = knowledge_revision_engine
        self.logger = get_logger("ConceptFormation")
        # Порог схожести для объединения концептов
        self.similarity_threshold = 2  # минимум общих свойств для создания гипотезы

    def analyze(self) -> List[Dict]:
        """
        Анализирует граф и предлагает новые концепты.
        Возвращает список гипотез о новых понятиях.
        """
        clusters = self._find_clusters()
        hypotheses = []
        for cluster in clusters:
            if len(cluster) >= 2:
                hypothesis = self._form_hypothesis(cluster)
                if hypothesis:
                    hypotheses.append(hypothesis)
        return hypotheses

    def _find_clusters(self) -> List[Set[str]]:
        """
        Находит группы узлов с общими свойствами или связями.
        """
        # Получаем все узлы с их свойствами
        node_properties: Dict[str, Set[str]] = defaultdict(set)
        edges = self.causal.get_edges()
        
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            relation = edge.get("relation", "")
            
            if not source or not target:
                continue
            
            # Для связей HAS_PROPERTY и IS_A собираем общие свойства
            if relation in ("HAS_PROPERTY", "IS_A"):
                node_properties[source].add(target)
        
        # Группируем узлы с общими свойствами
        clusters: List[Set[str]] = []
        processed: Set[str] = set()
        
        for node1, props1 in node_properties.items():
            if node1 in processed:
                continue
            cluster = {node1}
            processed.add(node1)
            
            for node2, props2 in node_properties.items():
                if node2 in processed:
                    continue
                common = props1 & props2
                if len(common) >= self.similarity_threshold:
                    cluster.add(node2)
                    processed.add(node2)
            
            if len(cluster) >= 2:
                clusters.append(cluster)
        
        return clusters

    def _form_hypothesis(self, cluster: Set[str]) -> Optional[Dict]:
        """
        Формирует гипотезу о новом концепте на основе кластера.
        """
        if len(cluster) < 2:
            return None
        
        # Собираем общие свойства всех узлов в кластере
        all_properties: List[Set[str]] = []
        for node in cluster:
            edges = self.causal.get_edges(source=node)
            props = set()
            for edge in edges:
                if edge.get("relation") in ("HAS_PROPERTY", "IS_A"):
                    props.add(edge.get("target", ""))
            all_properties.append(props)
        
        # Находим пересечение свойств
        common_properties = all_properties[0]
        for props in all_properties[1:]:
            common_properties = common_properties & props
        
        if not common_properties:
            return None
        
        # Предлагаем название для нового концепта
        cluster_list = sorted(cluster)
        suggested_name = f"категория({', '.join(cluster_list[:3])})"
        
        return {
            "type": "concept_formation",
            "suggested_concept": suggested_name,
            "members": cluster_list,
            "common_properties": list(common_properties),
            "confidence": min(0.5 + 0.1 * len(cluster), 0.9),
        }

    def apply(self, hypothesis: Dict) -> bool:
        """
        Применяет гипотезу: создаёт новый концепт в графе.
        """
        if not hypothesis:
            return False
        
        concept_name = hypothesis.get("suggested_concept", "")
        members = hypothesis.get("members", [])
        common_props = hypothesis.get("common_properties", [])
        confidence = hypothesis.get("confidence", 0.5)
        
        if not concept_name or len(members) < 2:
            return False
        
        # Создаём связи IS_A от каждого члена к новому концепту
        for member in members:
            self.causal.add_edge(member, concept_name, "IS_A", confidence=confidence)
        
        # Создаём связь HAS_PROPERTY от нового концепта к общим свойствам
        for prop in common_props:
            self.causal.add_edge(concept_name, prop, "HAS_PROPERTY", confidence=confidence)
        
        self.logger.info(f"Создан новый концепт: {concept_name} (членов: {len(members)}, свойств: {len(common_props)})")
        return True