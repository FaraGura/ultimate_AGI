# echo_core/knowledge_revision_engine.py
"""
Knowledge Revision Engine v1.0 — управление достоверностью знаний.
Обрабатывает подтверждение, опровержение, исключения и устаревание фактов.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from utils.utils_logger import get_logger


class KnowledgeRevisionEngine:
    STATUSES = {
        "confirmed": "Подтверждено пользователем",
        "rejected": "Опровергнуто пользователем",
        "outdated": "Устарело",
        "exception": "Имеет исключения",
        "uncertain": "Не уверена",
        "pending": "Ожидает проверки",
    }

    def __init__(self, db, causal_graph, belief_manager):
        self.db = db
        self.causal = causal_graph
        self.belief_manager = belief_manager
        self.logger = get_logger("KnowledgeRevision")
        self._create_tables()

    def _create_tables(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_source TEXT NOT NULL,
                fact_target TEXT NOT NULL,
                fact_relation TEXT NOT NULL,
                old_confidence REAL,
                new_confidence REAL,
                status TEXT DEFAULT 'pending',
                reason TEXT,
                user_feedback TEXT,
                timestamp TEXT
            )
        """)

    def revise(self, source: str, target: str, relation: str,
               feedback: str, user_text: str = "") -> Optional[Dict[str, Any]]:
        """
        Обрабатывает обратную связь от пользователя.
        feedback: "верно", "неверно", "не совсем", "устарело", "не уверен"
        """
        feedback_lower = feedback.lower().strip()

        # Получаем текущее состояние факта
        existing = self.causal.get_edges(source=source, target=target, relation=relation)
        old_confidence = existing[0].get("confidence", 0.5) if existing else 0.5

        if feedback_lower in ("верно", "правильно", "да", "верно.", "правильно."):
            return self._confirm(source, target, relation, old_confidence, user_text)
        elif feedback_lower in ("неверно", "неправильно", "нет", "ошибка", "неверно.", "неправильно."):
            return self._reject(source, target, relation, old_confidence, user_text)
        elif feedback_lower in ("не совсем", "частично", "есть исключение"):
            return self._add_exception(source, target, relation, old_confidence, user_text)
        elif feedback_lower in ("устарело", "уже не актуально"):
            return self._mark_outdated(source, target, relation, old_confidence, user_text)
        elif feedback_lower in ("не уверен", "не уверена", "не знаю"):
            return self._mark_uncertain(source, target, relation, old_confidence, user_text)
        else:
            return None

    def _confirm(self, source, target, relation, old_confidence, user_text):
        new_confidence = min(1.0, old_confidence + 0.2)
        self.causal.update_confidence(source, target, relation, new_confidence - old_confidence)
        self._log_revision(source, target, relation, old_confidence, new_confidence, "confirmed", user_text)
        return {"status": "confirmed", "confidence": new_confidence}

    def _reject(self, source, target, relation, old_confidence, user_text):
        new_confidence = max(0.1, old_confidence - 0.4)
        self.causal.update_confidence(source, target, relation, new_confidence - old_confidence)
        self._log_revision(source, target, relation, old_confidence, new_confidence, "rejected", user_text)
        return {"status": "rejected", "confidence": new_confidence}

    def _add_exception(self, source, target, relation, old_confidence, user_text):
        new_confidence = max(0.3, old_confidence - 0.1)
        self.causal.update_confidence(source, target, relation, new_confidence - old_confidence)
        self._log_revision(source, target, relation, old_confidence, new_confidence, "exception", user_text)
        return {"status": "exception", "confidence": new_confidence}

    def _mark_outdated(self, source, target, relation, old_confidence, user_text):
        new_confidence = 0.1
        self.causal.update_confidence(source, target, relation, new_confidence - old_confidence)
        self._log_revision(source, target, relation, old_confidence, new_confidence, "outdated", user_text)
        return {"status": "outdated", "confidence": new_confidence}

    def _mark_uncertain(self, source, target, relation, old_confidence, user_text):
        new_confidence = max(0.2, old_confidence - 0.15)
        self.causal.update_confidence(source, target, relation, new_confidence - old_confidence)
        self._log_revision(source, target, relation, old_confidence, new_confidence, "uncertain", user_text)
        return {"status": "uncertain", "confidence": new_confidence}

    def _log_revision(self, source, target, relation, old_conf, new_conf, status, feedback):
        self.db.execute(
            """INSERT INTO knowledge_revisions
               (fact_source, fact_target, fact_relation, old_confidence, new_confidence,
                status, user_feedback, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, target, relation, old_conf, new_conf, status, feedback, datetime.now().isoformat())
        )
        self.logger.info(f"Ревизия: {source} -{relation}-> {target}: {status} (conf: {old_conf:.2f} → {new_conf:.2f})")