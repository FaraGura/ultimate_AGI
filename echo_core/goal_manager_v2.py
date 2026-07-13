# echo_core/goal_manager_v2.py
"""
Goal Manager v2.0 — динамическое целеполагание.
Порождает цели на основе любопытства, противоречий, пробелов в знаниях.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from utils.utils_logger import get_logger


class GoalType(Enum):
    CURIOSITY = "curiosity"
    CONTRADICTION = "contradiction"
    KNOWLEDGE_GAP = "knowledge_gap"
    USER_REQUEST = "user_request"
    CONSOLIDATION = "consolidation"
    EXPLORATION = "exploration"


@dataclass
class Goal:
    goal_id: int
    description: str
    goal_type: GoalType
    priority: float = 0.5
    active: bool = True
    created_at: str = ""
    progress: float = 0.0
    metadata: Dict = field(default_factory=dict)


class GoalManagerV2:
    def __init__(self, causal_graph, attention_system=None, concept_formation=None):
        self.causal = causal_graph
        self.attention = attention_system
        self.concept_formation = concept_formation
        self.logger = get_logger("GoalManagerV2")
        self.goals: List[Goal] = []
        self._id_counter = 0
        self._register_default_goals()

    def _register_default_goals(self):
        self.add_goal("Самосохранение и целостность", GoalType.USER_REQUEST, priority=1.0)
        self.add_goal("Обнаружение противоречий в знаниях", GoalType.CONTRADICTION, priority=0.8)
        self.add_goal("Поиск новых концептов", GoalType.CURIOSITY, priority=0.7)
        self.add_goal("Консолидация опыта в знания", GoalType.CONSOLIDATION, priority=0.5)

    def add_goal(self, description: str, goal_type: GoalType, priority: float = 0.5, metadata: Dict = None) -> int:
        g = Goal(
            goal_id=self._id_counter,
            description=description,
            goal_type=goal_type,
            priority=priority,
            metadata=metadata or {},
        )
        self.goals.append(g)
        self._id_counter += 1
        return g.goal_id

    def get_active_goals(self) -> List[Goal]:
        return [g for g in self.goals if g.active]

    def update_from_graph(self) -> List[Goal]:
        """
        Анализирует граф и порождает новые цели.
        """
        new_goals = []
        new_goals.extend(self._detect_knowledge_gaps())
        new_goals.extend(self._detect_curiosity_targets())
        return new_goals

    def _detect_knowledge_gaps(self) -> List[Goal]:
        """
        Находит концепты с малым количеством связей и создаёт цели на их изучение.
        """
        gaps = []
        edges = self.causal.get_edges()

        # Считаем связи для каждого концепта
        connection_counts: Dict[str, int] = {}
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source:
                connection_counts[source] = connection_counts.get(source, 0) + 1
            if target:
                connection_counts[target] = connection_counts.get(target, 0) + 1

        # Находим концепты с 1-2 связями
        for concept, count in connection_counts.items():
            if count <= 2 and len(concept) > 2:
                goal = self.add_goal(
                    f"Изучить концепт '{concept}' (связей: {count})",
                    GoalType.KNOWLEDGE_GAP,
                    priority=0.4 + 0.1 * (3 - count),
                    metadata={"concept": concept, "connection_count": count},
                )
                gaps.append(goal)

        return gaps

    def _detect_curiosity_targets(self) -> List[Goal]:
        """
        Находит необычные паттерны в графе и создаёт исследовательские цели.
        """
        targets = []
        edges = self.causal.get_edges()

        # Ищем концепты с необычными комбинациями связей
        concept_relations: Dict[str, set] = {}
        for edge in edges:
            source = edge.get("source", "")
            relation = edge.get("relation", "")
            if source and relation:
                if source not in concept_relations:
                    concept_relations[source] = set()
                concept_relations[source].add(relation)

        # Находим концепты с разнотипными связями (потенциально интересные)
        for concept, relations in concept_relations.items():
            if len(relations) >= 2:
                target = self.add_goal(
                    f"Исследовать связи концепта '{concept}'",
                    GoalType.CURIOSITY,
                    priority=0.3 + 0.05 * len(relations),
                    metadata={"concept": concept, "relations": list(relations)},
                )
                targets.append(target)

        return targets