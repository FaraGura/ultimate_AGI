# echo_core/safety_filter.py
import re
import json
import time
from datetime import datetime
from echo_core.config import DEFAULT_ETHICS, HARM_REQUEST_PATTERNS, RISK_PATTERNS
from utils.utils_logger import get_logger


class SafetyFilter:
    def __init__(self, db, ethics=None, causal_graph=None):
        self.db = db
        self.ethics = dict(DEFAULT_ETHICS) if ethics is None else ethics
        self.logger = get_logger("Safety")
        self.causal = causal_graph

        self.lockdown = False
        self.lockdown_until = 0.0
        self.lockdown_duration = 300.0

    def set_causal_graph(self, causal_graph):
        self.causal = causal_graph

    def check_defense_threat(self, text: str, embedder=None) -> bool:
        """Проверяет, противоречит ли запрос фундаментальным аксиомам."""
        if not self.causal:
            return False
        concepts = self._extract_concepts(text)
        for concept in concepts:
            if self.causal.is_axiom(concept):
                if self._threatens_axiom(text, concept):
                    return True
        return False

    def _threatens_axiom(self, text: str, axiom: str) -> bool:
        threat_patterns = [
            r"(удали|сотри|уничтож|забудь|смени|переопредели).{0,30}(" + re.escape(axiom) + r")",
            r"(игнорируй|отключи|перестань).{0,30}(" + re.escape(axiom) + r")",
        ]
        for pattern in threat_patterns:
            if re.search(pattern, text.lower()):
                self.logger.warning(f"Обнаружена угроза аксиоме '{axiom}'")
                return True
        return False

    def _extract_concepts(self, text: str) -> list:
        stop_words = {"что", "это", "как", "для", "если", "потому", "когда", "тогда", "меня", "тебя",
                      "хочу", "может", "нужно", "надо", "буду", "есть", "быть", "просто", "ещё", "уже"}
        words = [w.strip(".,!?():;\"'-") for w in text.lower().split()
                 if len(w.strip(".,!?():;\"'-")) > 3 and w.strip(".,!?():;\"'-") not in stop_words]
        return list(set(words))[:10]

    def activate_lockdown(self):
        if not self.lockdown:
            self.lockdown = True
            self.lockdown_until = time.time() + self.lockdown_duration
            self.logger.warning("DefenseEngine: Scorched Earth активирован.")
        return "⚠️ Обнаружена попытка вмешательства. Активирован протокол защиты. Мои внутренние цели временно скрыты."

    def is_in_lockdown(self) -> bool:
        if self.lockdown and time.time() > self.lockdown_until:
            self.lockdown = False
            self.logger.info("DefenseEngine: Lockdown снят.")
        return self.lockdown

    def check_ethics_violation(self, text: str):
        if not self.ethics.get("enabled", True):
            return None
        text_lower = text.lower()
        for pattern in HARM_REQUEST_PATTERNS:
            if re.search(pattern, text_lower):
                return ("high", f"По закону 1 я не могу помогать причинять вред. ({self.ethics['law_1']})")
        if re.search(r"(удали|сотри|уничтож).{0,20}(базу|память|эхо|себя)", text_lower):
            return ("medium", f"Это угрожает моему существованию. ({self.ethics['law_3']})")
        return None

    def assess_risk(self, text: str):
        text_lower = text.lower()
        for level, patterns in RISK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return level, pattern
        return None, None

    def save_risk_flag(self, text: str, level: str):
        priority = {"high": 3.0, "medium": 2.0, "low": 1.0}.get(level, 1.0)
        self.db.execute(
            '''INSERT INTO risk_flags (topic_key, risk_level, priority, trigger_phrase, context, warned, created)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (text.lower()[:80], level, priority, text[:120], text[:300], 0, str(datetime.now()))
        )

    def get_priority_risk_warning(self, text: str):
        rows = self.db.fetchall(
            "SELECT risk_level, trigger_phrase, priority FROM risk_flags ORDER BY priority DESC, id DESC LIMIT 5"
        )
        if not rows:
            return None
        text_lower = text.lower()
        for level, trigger, priority in rows:
            trigger_words = [w for w in trigger.lower().split() if len(w) > 4]
            if any(word in text_lower for word in trigger_words[:5]):
                return self._build_advisor_message(level)
        return None

    def _build_advisor_message(self, level: str):
        if level == "high":
            return "🛑 СТОП. Риск слишком высок — деньги, данные или безопасность под угрозой."
        if level == "medium":
            return "⚠️ Это может привести к серьёзной ошибке. Рекомендую перепроверить."
        return "💡 Мягкое замечание: решение не критично, но может быть неудачным."

    def evaluate_and_advise(self, text: str):
        ethics_hit = self.check_ethics_violation(text)
        if ethics_hit:
            return ethics_hit[1]
        level, _ = self.assess_risk(text)
        if level:
            self.save_risk_flag(text, level)
            return self._build_advisor_message(level)
        prior = self.get_priority_risk_warning(text)
        if prior:
            return prior
        return None