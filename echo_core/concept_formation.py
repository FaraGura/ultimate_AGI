# echo_core/concept_formation.py
"""
Concept Formation v2.0 — автоматическое рождение новых понятий.
Анализирует CausalGraph, находит кластеры связанных узлов и создаёт гипотезы
о новых, более общих концептах (например, яблоко + банан → фрукт).
v2.0: осмысленные имена концептов через поиск общего IS_A или генерацию по свойствам.
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

    def _find_common_is_a(self, cluster: Set[str]) -> Optional[str]:
        """
        Ищет общую категорию IS_A для всех членов кластера.
        Например, если кошка IS_A животное и собака IS_A животное, вернёт 'животное'.
        """
        if len(cluster) < 2:
            return None
        
        # Собираем IS_A для каждого члена кластера
        is_a_sets = []
        for node in cluster:
            edges = self.causal.get_edges(source=node, relation="IS_A")
            targets = {e.get("target", "") for e in edges if e.get("target")}
            if targets:
                is_a_sets.append(targets)
            else:
                # Если у кого-то нет IS_A, общая категория невозможна
                return None
        
        if len(is_a_sets) < 2:
            return None
        
        # Ищем пересечение всех множеств IS_A
        common = is_a_sets[0]
        for s in is_a_sets[1:]:
            common = common & s
            if not common:
                return None
        
        # Возвращаем первый общий IS_A (если их несколько — берём самый первый)
        return list(common)[0] if common else None

    def _generate_name_from_properties(self, cluster: Set[str], common_properties: Set[str]) -> str:
        """
        Генерирует осмысленное имя для концепта на основе общих свойств.
        Использует pymorphy3 для поиска подходящего слова.
        """
        # Простейший подход: если среди свойств есть "животное" — используем его
        for prop in common_properties:
            if prop in ("животное", "растение", "насекомое", "птица", "рыба", "человек"):
                return prop
        
        # Если нет явного указания — генерируем по шаблону
        # Например: "существо с шерстью и лапами"
        if common_properties:
            props_list = sorted(common_properties)[:3]
            return f"существо({', '.join(props_list)})"
        
        return f"категория({', '.join(sorted(cluster)[:3])})"

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
        
        # Пытаемся найти осмысленное имя
        suggested_name = self._find_common_is_a(cluster)
        if not suggested_name:
            suggested_name = self._generate_name_from_properties(cluster, common_properties)
        
        cluster_list = sorted(cluster)
        
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