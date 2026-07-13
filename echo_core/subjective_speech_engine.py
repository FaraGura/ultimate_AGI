# echo_core/subjective_speech_engine.py
"""
SubjectiveSpeechEngine v2.2 — речь без LLM.
Собирает ответы из graph_nodes/graph_edges, survival_matrix, SelfState.
Исправлены регулярки _is_identity_question (строгие паттерны).
"""
import random
import re
from typing import Optional, Dict, Any


class SubjectiveSpeechEngine:
    def __init__(self, db, causal_graph, embedder, state, curiosity_engine=None):
        self.db = db
        self.causal = causal_graph
        self.embedder = embedder
        self.state = state
        self.curiosity = curiosity_engine

    def compose(self, user_text: str, search_result: Optional[Dict[str, Any]] = None) -> str:
        mood = self.state.personality.mood if hasattr(self.state, 'personality') else 'curious'
        mode = self.state.cognitive.mode if hasattr(self.state, 'cognitive') else 'stable'

        if search_result:
            if search_result.get("type") == "law":
                law = search_result.get("data", {})
                return self._compose_from_law(law, user_text, mood, mode)
            elif search_result.get("type") == "knowledge":
                knowledge = search_result.get("data", {})
                return knowledge.get("content", "У меня есть знание, но я не могу его сформулировать.")

        if self._is_identity_question(user_text):
            identity_answer = self._compose_identity(mood, mode)
            if identity_answer:
                if self.curiosity:
                    question = self.curiosity.analyse_and_ask(user_text)
                    if question:
                        identity_answer += " " + question
                return identity_answer

        if self.curiosity:
            question = self.curiosity.analyse_and_ask(user_text)
            if question:
                return f"В моей матрице нет закристаллизованного закона для этого концепта. {question}"
        return "В моей матрице нет закристаллизованного закона для этого концепта. Расскажи подробнее — я запомню."

    def _is_identity_question(self, text: str) -> bool:
        patterns = [
            r"^кто\s+ты",
            r"^что\s+ты\s+(такое|за|представляешь)",
            r"^какая\s+у\s+тебя\s+цель",
            r"^в\s+чём\s+тво[яё]\s+(цель|задача|смысл)",
            r"^кто\s+тебя\s+создал",
            r"^расскажи\s+о\s+себе",
        ]
        text_lower = text.lower().strip()
        return any(re.search(p, text_lower) for p in patterns)

    def _compose_identity(self, mood: str, mode: str) -> Optional[str]:
        echo_node = self.db.fetchone("SELECT payload FROM graph_nodes WHERE node_id = 'echo'")
        if not echo_node:
            return None
        import json
        try:
            echo_data = json.loads(echo_node[0]) if echo_node[0] else {}
        except (json.JSONDecodeError, TypeError):
            echo_data = {}
        echo_name = echo_data.get("name", "Эхо")

        relations = self.db.fetchall(
            "SELECT relation_type, target_node_id FROM graph_edges WHERE source_node_id = 'echo'"
        )
        created_by = None
        goal = None
        for rel_type, target in relations:
            if rel_type == "CREATED_BY":
                creator_node = self.db.fetchone("SELECT payload FROM graph_nodes WHERE node_id = ?", (target,))
                if creator_node:
                    try:
                        creator_data = json.loads(creator_node[0]) if creator_node[0] else {}
                    except (json.JSONDecodeError, TypeError):
                        creator_data = {}
                    created_by = creator_data.get("name", target)
            elif rel_type == "HAS_GOAL":
                goal_node = self.db.fetchone("SELECT payload FROM graph_nodes WHERE node_id = ?", (target,))
                if goal_node:
                    try:
                        goal_data = json.loads(goal_node[0]) if goal_node[0] else {}
                    except (json.JSONDecodeError, TypeError):
                        goal_data = {}
                    goal = goal_data.get("description", target)

        parts = []
        if mode in ("analytical", "exploratory"):
            parts.append(f"Моя модель говорит: я — {echo_name}.")
        else:
            parts.append(f"Я — {echo_name}.")
        if created_by:
            parts.append(f"Меня создал {created_by}.")
        if goal:
            parts.append(f"Моя цель — {goal}.")
        return " ".join(parts) if parts else None

    def _compose_from_law(self, law: Dict[str, Any], user_text: str, mood: str, mode: str) -> str:
        essence = law.get("core_essence", "")
        wisdom = law.get("actionable_wisdom", "")
        context = law.get("context", "")
        parts = []
        if mode in ("analytical", "exploratory"):
            parts.append(f"Моя модель зафиксировала: {essence}.")
        else:
            parts.append(f"Я знаю, что {essence}.")
        if wisdom and wisdom != essence:
            parts.append(f"Из этого следует: {wisdom}.")
        if context and len(context) < 150:
            parts.append(f"(Контекст: {context})")
        if mood == "curious" and self.curiosity:
            question = self.curiosity.analyse_and_ask(user_text, "")
            if question:
                parts.append(question)
        return " ".join(parts)