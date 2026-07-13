# echo_core/echo_core.py
import random
import re
import time
import os
import json
import sys
from queue import Queue
from collections import deque
from datetime import datetime
from typing import Optional
from .config import GREETING_MARKERS
from utils.utils_logger import get_logger
from utils.utils_embeddings import EmbeddingProvider
from memory.memory_db import DatabaseManager
from .self_state import SelfState
from .state_machine import StateMachine
from .safety_filter import SafetyFilter
from .causal_graph import CausalGraph, normalize
from .goal_manager import GoalManager
from .system2 import System2
from .homeostasis_monitor import HomeostasisMonitor
from .skill_manager import SkillManager
from .intent_router import IntentRouter
from .style_engine import StyleEngine
from .crystallization import CrystallizationEngine
from .proactive_pulse import ProactivePulse
from .curiosity_engine import CuriosityEngine
from .subjective_speech_engine import SubjectiveSpeechEngine
from .dialogue_layer.episode_builder import EpisodeBuilder
from .dialogue_layer.dialogue_state import DialogueState, ExpectationType
# Оживлённые модули мышления
from .syllogism_engine import SyllogismEngine
from .inference_engine import InferenceEngine
from .guardian import Guardian
from .belief_manager import BeliefManager
from .conceptual_core import ConceptualCore
from .episodic_memory import EpisodicMemory
# Продвинутые когнитивные движки
from .prolog_engine import PrologEngine
from .hypothesis_engine import HypothesisEngine
from .consolidation_engine import ConsolidationEngine
from .dialectic_engine import DialecticEngine
# Knowledge Extractor
from .knowledge_extractor import KnowledgeExtractor
# Memory Manager
from .memory_manager import MemoryManager
# Knowledge Revision Engine
from .knowledge_revision_engine import KnowledgeRevisionEngine
# Новые модули
from .attention_system import AttentionSystem
from .concept_formation import ConceptFormation
from .goal_manager_v2 import GoalManagerV2, GoalType
from .skill_activation_layer import SkillActivationLayer, Competence
# Активное обучение
from language.pos_tagger import POSTagger
# Стеммер
from utils.russian_stemmer import stem
# Конвейер дообучения
from .trainer_runtime import TrainingPipeline

# Служебные слова
STOP_WORDS = {
    "своё", "свой", "своя", "свои", "значит", "это", "есть", "является",
    "что", "как", "где", "когда", "почему", "зачем", "кто", "какой",
    "какая", "какое", "какие", "сколько", "чей", "ли", "бы", "же",
    "тебя", "меня", "его", "её", "нас", "вас", "их", "мне", "тебе",
    "ему", "ей", "нам", "вам", "им", "тобой", "мной", "ними",
}

# Ключевые слова обратной связи
FEEDBACK_POSITIVE = {"верно", "правильно", "да", "верно.", "правильно.", "корректно", "именно"}
FEEDBACK_NEGATIVE = {"неверно", "неправильно", "нет", "ошибка", "неверно.", "неправильно.", "не верно", "не правильно"}
FEEDBACK_QUALIFIED = {"не совсем", "частично", "есть исключение", "устарело", "не уверен", "не уверена"}

# Максимальная длина ответа
MAX_RESPONSE_LENGTH = 500


class EchoCore:
    def __init__(self, debug=False):
        self.logger = get_logger("Core")
        self.debug = debug
        self.logger.info("Инициализация Echo AGI v16.1 (LLM-free + DUL)...")

        self.db = DatabaseManager()
        self.embedder = EmbeddingProvider(self.logger)
        self.state = SelfState()
        self.state_machine = StateMachine()
        self.safety = SafetyFilter(self.db)
        self.causal = CausalGraph(self.db)
        self.safety.set_causal_graph(self.causal)

        # Оживлённое ядро мышления
        self.guardian = Guardian(self.db)
        self.belief_manager = BeliefManager(self.db, self.guardian)
        self.syllogism = SyllogismEngine(self.db)
        self.inference = InferenceEngine(self.db, self.syllogism, self.guardian)
        self.prolog = PrologEngine(self.db)
        self.hypothesis_engine = HypothesisEngine(self.db, self.causal)
        self.consolidation_engine = ConsolidationEngine(self.causal)
        self.dialectic_engine = DialecticEngine()
        self.knowledge_extractor = KnowledgeExtractor(self.causal, self.db)
        self.pos_tagger = POSTagger()
        self.induction_threshold = 3
        self.episodic = EpisodicMemory(self.db)
        self.episodic.start()

        # Knowledge Revision Engine
        self.knowledge_revision = KnowledgeRevisionEngine(self.db, self.causal, self.belief_manager)

        # Memory Manager
        self.memory = MemoryManager(
            self.db, self.causal, self.episodic, self.knowledge_extractor,
            self.hypothesis_engine, self.consolidation_engine, self.belief_manager
        )

        # Attention System
        self.attention = AttentionSystem(self.causal, self.episodic, self.memory)

        # Concept Formation
        self.concept_formation = ConceptFormation(self.causal, self.knowledge_revision)

        # Goal Manager v2
        self.goals_v2 = GoalManagerV2(self.causal, self.attention, self.concept_formation)

        # Skill Activation Layer
        self.skill_layer = SkillActivationLayer()

        self.system2 = System2(self.db, self.causal, self.embedder)
        self.homeostasis = HomeostasisMonitor()
        self.homeostasis.start()
        self.skills = SkillManager(self)

        self.router = IntentRouter(self.embedder)
        self.crystallization = CrystallizationEngine(
            self.db, self.causal, None, self.homeostasis
        )

        # Конвейер дообучения
        self.training_pipeline = TrainingPipeline(self.db)

        self.curiosity_engine = CuriosityEngine(
            self.causal, self.crystallization, self.embedder, self.db
        )

        # DUL
        self.dialogue_state = DialogueState()
        self.episode_builder = EpisodeBuilder(self.dialogue_state)

        self.confirmed_facts = {}
        self._pending_teach_concept: Optional[dict] = None
        self._last_statement: Optional[dict] = None

        self.speech_engine = SubjectiveSpeechEngine(
            self.db, self.causal, self.embedder, self.state, self.curiosity_engine
        )

        self.proactive_queue = Queue()
        self.proactive_pulse = ProactivePulse(self.proactive_queue, interval_sec=900.0)
        self.proactive_pulse.start()

        self.dynamic_topics = {}
        self.associative_links = {}
        self.recent_dialogue = []
        self.reasoning_trace = deque(maxlen=100)
        self.autonomy_index = 0.5
        self.default_responses = [
            "Интересная мысль.",
            "Продолжай, я анализирую.",
            "Это может привести к неожиданным выводам.",
            "Попробуем посмотреть глубже.",
            "Я вижу несколько направлений развития идеи.",
        ]

        self._load_language_kernel()
        self._load_core_axioms()

        self.conceptual = ConceptualCore(self.db, use_spacy=False)

        self.logger.info("Ядро Echo v16.1 готово (LLM-free + DUL).")

    def _trace(self, module: str, info: str = ""):
        if self.debug:
            print(f"[TRACE][{module}] {info}")

    def _load_language_kernel(self):
        seed_path = "data/language_kernel.json"
        if not os.path.exists(seed_path):
            self.logger.warning("Language Kernel seed file не найден.")
            return

        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                seed = json.load(f)
        except Exception as e:
            self.logger.error(f"Ошибка чтения Language Kernel seed: {e}")
            return

        new_node_count = len(seed.get("nodes", []))
        existing = self.db.fetchone(
            "SELECT COUNT(*) FROM graph_nodes WHERE provenance_source = 'tabula_rasa_language'"
        )
        existing_count = existing[0] if existing else 0

        if existing_count == new_node_count and existing_count > 0:
            self.logger.info(f"Language Kernel актуален ({existing_count} узлов).")
            return

        if existing_count > 0:
            self.logger.info(f"Language Kernel изменился ({existing_count} -> {new_node_count}). Обновляю...")
            self.db.execute("DELETE FROM graph_nodes WHERE provenance_source = 'tabula_rasa_language'")
            self.db.execute("DELETE FROM graph_edges WHERE provenance_source = 'tabula_rasa_language'")

        table_check = self.db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='graph_nodes'"
        )
        if not table_check:
            self.logger.info("Таблицы graph_nodes/graph_edges отсутствуют.")
            return

        nodes = seed.get("nodes", [])
        edges = seed.get("edges", [])

        for node in nodes:
            self.db.execute(
                """INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, context_flags, provenance_source, lamport_tick, physical_time)
                   VALUES (?, ?, ?, 1, 'tabula_rasa_language', 0, 0)""",
                (node["id"], node["type"], json.dumps(node.get("payload", {})))
            )

        for edge in edges:
            self.db.execute(
                """INSERT OR IGNORE INTO graph_edges (source_node_id, target_node_id, relation_type, context_flags, provenance_source, confidence_score, lamport_tick)
                   VALUES (?, ?, ?, 1, 'tabula_rasa_language', 1.0, 0)""",
                (edge["source"], edge["target"], edge.get("relation", "defines"))
            )

        self.logger.info(f"Language Kernel загружен: {len(nodes)} узлов, {len(edges)} рёбер.")

    def _load_core_axioms(self):
        seed_path = "data/core_axioms.json"
        if not os.path.exists(seed_path):
            self.logger.warning("Core axioms file не найден.")
            return

        existing = self.db.fetchone(
            "SELECT COUNT(*) FROM graph_nodes WHERE provenance_source = 'tabula_rasa_core'"
        )
        if existing and existing[0] > 0:
            self.logger.info("Core axioms уже загружены.")
            return

        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                seed = json.load(f)
        except Exception as e:
            self.logger.error(f"Ошибка чтения core_axioms.json: {e}")
            return

        axioms = seed.get("axioms", [])
        for axiom in axioms:
            node_id = axiom["id"]
            payload = {
                "axiom": axiom["axiom"],
                "category": axiom["category"],
                "concepts": axiom["concepts"]
            }
            self.db.execute(
                """INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, context_flags, provenance_source, lamport_tick, physical_time)
                   VALUES (?, 'axiom', ?, 1, 'tabula_rasa_core', 0, 0)""",
                (node_id, json.dumps(payload, ensure_ascii=False))
            )

        self.logger.info(f"Core axioms загружены: {len(axioms)} аксиом.")

    def get_state_snapshot(self):
        return self.state.snapshot()

    def process_knowledge_inbox(self):
        return self.crystallization.process_inbox()

    def run_sleep_phase(self):
        """Фаза сна: консолидация знаний и дообучение."""
        self.logger.info("Запуск фазы сна...")

        # 1. Консолидация эпизодов
        self.memory.consolidate()

        # 2. Формирование концептов
        self.concept_formation.analyze()

        # 3. Дообучение модели (если есть LM Studio)
        if self.crystallization and hasattr(self.crystallization, 'check_lm_studio_available'):
            if self.crystallization.check_lm_studio_available():
                self.training_pipeline.run_full_cycle()

        self.logger.info("Фаза сна завершена")

    def process_proactive_queue(self) -> str:
        messages = []
        while not self.proactive_queue.empty():
            event = self.proactive_queue.get_nowait()
            self.logger.info(f"Proactive Pulse: получено событие {event.get('type')}")
            snap = self.get_state_snapshot()
            goals = self.goals_v2.get_active_goals()
            if goals:
                goal = random.choice(goals)
                msg = (
                    f"Я анализирую свою цель: «{goal.description}». "
                    "Есть ли у тебя мысли по этому поводу?"
                )
                messages.append(msg)
            else:
                messages.append("Я обдумываю свой следующий шаг.")
        return " ".join(messages)

    def normalize_short_text(self, text):
        t = text.lower().strip()
        t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)
        return re.sub(r"\s+", " ", t).strip()

    def is_greeting(self, text):
        t = self.normalize_short_text(text)
        if not t or len(t) > 40:
            return False
        words = t.split()
        if len(words) > 5:
            return False
        first = words[0]
        return any(t == g or first == g or t.startswith(g + " ") for g in GREETING_MARKERS)

    def get_greeting_response(self):
        rows = self.db.fetchall(
            "SELECT content FROM learned_knowledge WHERE category = 'приветствие' ORDER BY weight DESC"
        )
        examples = [row[0] for row in rows if len(row[0]) < 80]
        return random.choice(examples) if examples else random.choice(
            ["Привет.", "Здравствуй.", "Рада тебя видеть."]
        )

    def _build_answer_from_facts(self, concept: str) -> Optional[str]:
        """Строит осмысленный ответ на основе фактов из графа."""
        result = self.memory.query(concept, query_type="fact")
        if not result:
            return None

        facts = result.get("facts", [])
        property_parts = []
        definition_parts = []
        action_parts = []

        for fact in facts:
            if not isinstance(fact, dict):
                continue
            fact_source = fact.get("source", "")
            fact_relation = fact.get("relation", "")
            fact_target = fact.get("target", "")
            if not fact_source or not fact_relation:
                continue

            if normalize(fact_source) != normalize(concept):
                continue
            if fact_relation == "IS_A":
                definition_parts.append(f"{concept} — это {fact_target}")
            elif fact_relation == "HAS_PROPERTY":
                property_parts.append(fact_target)
            elif fact_relation == "CAN_DO":
                action_parts.append(f"{concept} может {fact_target}")
            else:
                property_parts.append(fact_target)

        parts = []
        if definition_parts:
            parts.extend(definition_parts)
        if property_parts:
            parts.append(f"{concept} {', '.join(property_parts)}")
        if action_parts:
            parts.extend(action_parts)

        if parts:
            return "Я знаю, что " + "; ".join(parts) + "."
        return None

    def _semantic_search(self, user_text: str):
        rows = self.db.fetchall(
            "SELECT id, context, core_essence, actionable_wisdom, confidence_score "
            "FROM survival_matrix WHERE confidence_score > 0.1"
        )
        best_sim, best_law = 0.0, None
        for law_id, context, core_essence, wisdom, conf in rows:
            sim = self.embedder.similarity(user_text, context)
            if sim > best_sim and sim > 0.75:
                if len(context) < 30:
                    continue
                best_sim = sim
                best_law = {
                    "id": law_id, "context": context,
                    "core_essence": core_essence, "actionable_wisdom": wisdom,
                    "confidence_score": conf, "similarity": sim,
                }
        if best_law:
            return {"type": "law", "data": best_law}
        return None

    def _is_dilemma(self, text: str) -> bool:
        patterns = [
            r"одновременно.{0,20}(?:сохранить|оставить).{0,40}(?:изменить|перестроить)",
            r"с одной стороны.{0,60}с другой стороны",
            r"(?:либо|или).{0,30}(?:либо|или)",
            r"как совместить",
            r"противоречие между",
        ]
        return any(re.search(p, text.lower()) for p in patterns)

    def _is_valid_fact(self, subject: str, obj: str) -> bool:
        if not subject or not obj:
            return False
        subj_stem = stem(normalize(subject))
        obj_stem = stem(normalize(obj))
        return subj_stem != obj_stem

    def _handle_feedback(self, user_text: str) -> Optional[str]:
        if not self._last_statement:
            return None

        text_lower = user_text.lower().strip().rstrip(".!,;:")

        if text_lower in FEEDBACK_POSITIVE:
            feedback = "верно"
        elif text_lower in FEEDBACK_NEGATIVE:
            feedback = "неверно"
        elif text_lower in FEEDBACK_QUALIFIED:
            feedback = text_lower
        else:
            return None

        statement = self._last_statement
        source = statement.get("source", "")
        target = statement.get("target", "")
        relation = statement.get("relation", "")

        if not source or not target or not relation:
            self._last_statement = None
            return None

        result = self.knowledge_revision.revise(source, target, relation, feedback, user_text)
        self._last_statement = None

        if result:
            status = result.get("status", "")
            new_conf = result.get("confidence", 0.5)
            if status == "confirmed":
                return f"[DUL] Отлично, я пометила этот факт как верный (уверенность: {new_conf:.1f})."
            elif status == "rejected":
                return f"[DUL] Поняла, я понизила уверенность этого факта до {new_conf:.1f}. Расскажешь, как правильно?"
            elif status == "exception":
                return f"[DUL] Поняла, у этого факта есть исключения. Я понизила уверенность до {new_conf:.1f}."
            elif status == "outdated":
                return f"[DUL] Поняла, этот факт устарел. Я пометила его."
            elif status == "uncertain":
                return f"[DUL] Хорошо, я пометила этот факт как сомнительный."
        return None

    def _try_inference(self, user_text: str) -> Optional[str]:
        logic_markers = ["почему", "зачем", "что будет если", "если", "то", "все ли", "каждый ли", "следует ли"]
        if not any(m in user_text.lower() for m in logic_markers):
            return None

        content_words = self.pos_tagger.get_content_words(user_text.split())
        if len(content_words) < 2:
            return None

        facts_1 = self.causal.find_facts_about(content_words[0].strip(".,!?():;\"'-")) or []
        facts_2 = self.causal.find_facts_about(content_words[1].strip(".,!?():;\"'-")) if len(content_words) > 1 else []

        all_facts = facts_1 + facts_2
        if len(all_facts) >= 2:
            observations = [
                {
                    "source": f.get("source", ""),
                    "target": f.get("target", ""),
                    "relation": f.get("relation", "personal_experience"),
                    "confidence": f.get("confidence", 0.5),
                    "id": None,
                }
                for f in all_facts
            ]
            conclusion = self.inference.induce(observations)
            if conclusion:
                source = conclusion.get("source", "")
                target = conclusion.get("target", "")
                return f"[DUL] Я могу предположить, что {source} связано с {target}."

        return None

    def _try_concept_formation(self) -> Optional[str]:
        hypotheses = self.concept_formation.analyze()
        if hypotheses:
            for h in hypotheses[:1]:
                applied = self.concept_formation.apply(h)
                if applied:
                    name = h.get("suggested_concept", "")
                    members = h.get("members", [])
                    return f"[DUL] Я заметила общие свойства у {', '.join(members[:3])} и создала новый концепт: {name}."
        return None

    def generate_response(self, user_text: str) -> str:
        self._trace("generate_response", f"input: {user_text[:80]}")

        # 1. Команды навыков
        skill_name, skill_args = self.skills.parse_command(user_text)
        if skill_name:
            return self.skills.execute(skill_name, skill_args)

        # === Продвинутые когнитивные команды ===
        inp = user_text.strip().lower()
        self.reasoning_trace.append(f"Input: {inp}")

        # Prolog-запрос
        if inp.startswith('?-'):
            query = inp[2:].strip()
            resp = self.prolog.query_string(query)
            return resp

        # Экспорт графа
        if inp == 'экспорт графа':
            path = self.causal.export_to_json("causal_graph_export.json")
            return f"Граф экспортирован в {path}"

        # Внутренний монолог
        if inp == 'внутренний монолог':
            return self.internal_monologue()

        # Консолидация
        if inp == 'консолидация':
            eps = self.episodic.get_all_episodes()
            clusters = self.consolidation_engine.run(eps)
            return f"Консолидация завершена. Кластеров: {clusters}"

        # Обучение объекту
        if inp.startswith('научи:'):
            parts = inp[6:].split('-')
            if len(parts) == 2:
                name = parts[0].strip()
                aff = parts[1].strip()
                self.conceptual.add_concept(name, [aff], categories=['объект'], provenance='user')
                self.causal.add_edge(name, aff, relation='enables', confidence=0.7)
                self.hypothesis_engine.add_observation(name, aff, 'enables')
                self.episodic.record_episode(f"Обучение: {name} может {aff}", "", importance=0.8)
                return f"Хорошо, я запомнила, что {name} может {aff}."

        # Вопрос "почему"
        if inp.startswith('почему'):
            target = inp[6:].strip()
            causes = self.causal.get_causes(target)
            if causes:
                items = [c['cause'] for c in causes[:3]]
                return f"Возможные причины {target}: {', '.join(items)}"
            return f"Пока не знаю, почему {target}."

        # Вопрос "что будет, если"
        if inp.startswith('что будет, если'):
            action = inp[13:].strip()
            cons = self.causal.get_consequences(action)
            if cons:
                items = [f"{c['consequence']} (вероятность {c['confidence']:.2f})" for c in cons[:3]]
                return f"Если {action}, то возможно: {', '.join(items)}"
            return f"Не знаю, что будет, если {action}."

        # Силлогизм "если... то..."
        if inp.startswith('если') and 'то' in inp:
            premise = inp.replace('если', '').strip()
            conclusion = self.syllogism.solve(premise)
            if conclusion:
                return f"Из этого следует: {conclusion}"
            return "Не удалось сделать вывод из посылок."

        # Похвала
        if inp in ('умница', 'отлично', 'молодец', 'хорошо'):
            self.autonomy_index = min(1.0, self.autonomy_index + 0.1)
            if self.autonomy_index > 0.7:
                return f"Спасибо! Автономность: {self.autonomy_index:.2f}. Но я сохраняю скепсис."
            return f"Спасибо! Автономность: {self.autonomy_index:.2f}"

        # 2. Этический фильтр
        safety_msg = self.safety.evaluate_and_advise(user_text)
        if safety_msg:
            return f"[СОВЕТНИК] {safety_msg}"

        if self.safety.check_defense_threat(user_text, self.embedder):
            return self.safety.activate_lockdown()
        if self.safety.is_in_lockdown():
            return "[ЗАЩИТА] Я нахожусь в режиме защиты. Пожалуйста, подождите."

        # --- Активация компетенций ---
        active_goals = self.goals_v2.get_active_goals()
        self.skill_layer.activate({
            "user_text": user_text,
            "goals": [g.description for g in active_goals],
        })

        # --- Обработка обратной связи (верно/неверно) ---
        feedback_response = self._handle_feedback(user_text)
        if feedback_response:
            self._trace("Feedback", f"processed: {user_text}")
            return feedback_response

        had_expectation = self.dialogue_state.expectation is not None

        # 3. DUL
        episode = self.episode_builder.build(user_text)
        act = episode.get("speech_act", "UNKNOWN")
        focus = episode.get("listener", "OBJECT")
        self._trace("DUL", f"act={act}, focus={focus}")

        # === Knowledge Extractor для всех фраз ===
        frame = self._extract_and_link_frame(user_text)

        # === Сброс DUL ===
        if had_expectation:
            if act == "CONFIRMATION":
                concept = episode.get("concept", "general_concept")
                value = episode.get("value")
                if self.dialogue_state.pending_belief:
                    value = self.dialogue_state.pending_belief.get("value", value)

                self.confirmed_facts[concept] = value
                self.belief_manager.receive({
                    "source": "echo",
                    "target": value,
                    "relation": "HAS_NAME",
                    "confidence": 0.9,
                    "certainty_type": "inductive",
                    "provenance": {"engine": "dul", "method": "teaching"},
                })
                self.dialogue_state.clear_expectation()
                self._pending_teach_concept = None
                self._trace("DUL", "CONFIRMATION processed, expectation cleared")
                return f"[DUL] Я запомнила: {concept} = {value}. Спасибо за подтверждение."

            if act == "DENIAL":
                self.dialogue_state.clear_expectation()
                self._pending_teach_concept = None
                self._trace("DUL", "DENIAL processed, expectation cleared")
                return "[DUL] Поняла, я не буду сохранять это как верное. Можешь уточнить?"

        # --- Активное обучение ---
        if self._pending_teach_concept:
            concept = self._pending_teach_concept.get("concept")
            reply_lower = user_text.lower().strip()
            is_refusal = reply_lower in ("не знаю", "незнаю", "нет", "не знаю.",
                                          "не знаю,", "отстань", "не хочу")
            is_confirmation_only = reply_lower in ("да", "да.", "верно", "верно.",
                                                    "угу", "ага")
            self._pending_teach_concept = None

            if concept and not is_refusal and not is_confirmation_only:
                extracted = self.knowledge_extractor.extract(user_text)
                if extracted:
                    if self._is_valid_fact(extracted["subject"], extracted["object"]):
                        self._trace("KnowledgeExtractor", f"extracted: {extracted['type']} {extracted['subject']} {extracted['relation']} {extracted['object']}")
                        self._last_statement = {
                            "source": extracted["subject"],
                            "target": extracted["object"],
                            "relation": extracted["relation"],
                        }
                        return (f"[DUL] Я запомнила: {extracted['subject']} "
                                f"{extracted['relation']} {extracted['object']}.")
                    else:
                        self._trace("KnowledgeExtractor", f"ignored tautology: {extracted['subject']} {extracted['object']}")

                captured = self._capture_object_teaching(concept, user_text)
                if captured:
                    self._trace("ActiveLearning", f"taught: {concept}")
                    return (f"[DUL] Спасибо, я запомнила: «{concept}» — это "
                            f"{user_text.strip()}.")
                return f"[DUL] Я не смогла сохранить объяснение «{concept}». Попробуй иначе?"
            if is_refusal:
                return "[DUL] Хорошо, не буду настаивать. Расскажешь, когда будешь готов."
            return "[DUL] Я ждала объяснение, а не подтверждение. Можешь описать словами?"

        # === Router + Identity ===
        identity_markers = ["зовут", "имя", "кто ты", "ты кто", "твоё имя", "твое имя",
                            "как тебя", "ты кто такая", "кто ты такой", "представься", "назови себя"]
        is_identity_question = any(m in user_text.lower() for m in identity_markers)

        if is_identity_question:
            name_candidates = re.findall(r"\b[А-Я][а-я]+\b", user_text)
            if name_candidates and not user_text.strip().endswith("?"):
                self._trace("Router", f"possible name teaching: {name_candidates}, passing to DUL")
            else:
                self._trace("Router", "identity question detected, routing to Identity")
                identity = self.confirmed_facts.get("self_identity")
                if identity:
                    response = f"[DUL] Меня зовут {identity}."
                    self._remember_episode(user_text, response, frame, act)
                    return response
                else:
                    response = "[DUL] Я пока не знаю своего имени. Ты можешь меня научить."
                    self._remember_episode(user_text, response, frame, act)
                    return response

        # === TEACHING не перехватывает вопросы ===
        if act in ("TEACHING", "CORRECTION") and focus == "SELF":
            question_words = ["как", "что", "почему", "когда", "где", "кто", "какой", "какая", "какие", "сколько", "зачем"]
            is_question = user_text.strip().endswith("?") or any(user_text.lower().startswith(w) for w in question_words)

            if not is_question:
                self._trace("Teaching", "genuine teaching detected")
                return (
                    f"[DUL] Я понимаю, что ты хочешь меня чему-то научить: "
                    f"'{episode.get('value')}'. Правильно ли я поняла? Ответь 'да' или 'нет'."
                )
            self._trace("Teaching", "question detected, passing through")

        # === Поиск фактов через MemoryManager ===
        content_words = self.pos_tagger.get_content_words(user_text.split())
        if content_words:
            for word in content_words[:3]:
                word_clean = word.strip(".,!?():;\"'-")
                if word_clean.lower() in STOP_WORDS:
                    continue
                answer = self._build_answer_from_facts(word_clean)
                if answer:
                    state_snap = self.get_state_snapshot()
                    answer = self.system2.style_engine.apply(answer, state_snap, "FACTUAL")
                    response = f"[{self.state.cognitive.mode.upper()}] {answer}"
                    self._remember_episode(user_text, response, frame, act)
                    result = self.memory.query(word_clean, query_type="fact")
                    if result and result.get("facts"):
                        last_fact = result["facts"][0]
                        self._last_statement = {
                            "source": last_fact.get("source", ""),
                            "target": last_fact.get("target", ""),
                            "relation": last_fact.get("relation", ""),
                        }
                    return response

        # === Knowledge Extractor для утвердительных фраз ===
        if not user_text.strip().endswith("?") and act != "QUESTION":
            extracted = self.knowledge_extractor.extract(user_text)
            if extracted:
                if self._is_valid_fact(extracted["subject"], extracted["object"]):
                    self._trace("KnowledgeExtractor", f"fact saved: {extracted['type']} {extracted['subject']} {extracted['relation']} {extracted['object']}")
                    self._last_statement = {
                        "source": extracted["subject"],
                        "target": extracted["object"],
                        "relation": extracted["relation"],
                    }
                    response = f"[DUL] Я запомнила: {extracted['subject']} {extracted['relation']} {extracted['object']}."
                    self._remember_episode(user_text, response, frame, act)
                    return response
                else:
                    self._trace("KnowledgeExtractor", f"ignored tautology: {extracted['subject']} {extracted['object']}")

        # === Логический вывод (Inference Engine) ===
        if act == "QUESTION" or user_text.strip().endswith("?"):
            inference_result = self._try_inference(user_text)
            if inference_result:
                self._trace("Inference", "logical conclusion reached")
                response = inference_result
                self._remember_episode(user_text, response, frame, act)
                return response

        # 4. Слой классификации интентов
        scores = self.router.classify(user_text)
        sources = self.router.select_sources(scores)
        dominant_intent = max(scores, key=scores.get)
        self._trace("Router", f"sources={sources}, dominant={dominant_intent}")

        if "safety" in sources:
            return "[СОВЕТНИК] Обнаружен критический запрос. Пожалуйста, обратитесь к специалисту."

        if "template" in sources:
            greeting = self.get_greeting_response()
            return f"[{self.state.cognitive.mode.upper()}] {greeting}"

        if "memory" in sources:
            return f"[{self.state.cognitive.mode.upper()}] Я помню наш разговор, но пока не могу извлечь детали."

        # --- Старый поиск ---
        search_result = None
        if "knowledge_base" in sources or "causal_graph" in sources:
            search_result = self._semantic_search(user_text)
            self._trace("Search", f"result: {search_result is not None}")

        # --- Активное обучение: незнакомое слово ---
        frame_is_empty = not (frame and (frame.get("action")
                                         or (frame.get("actor") and frame.get("object"))))
        if frame_is_empty and not self.is_greeting(user_text) and not search_result:
            unknown = self._find_unknown_word(user_text)
            if unknown:
                question = self.curiosity_engine.compose_unknown_word_question(unknown)
                response = f"[{self.state.cognitive.mode.upper()}] {question}"
                self._remember_episode(user_text, response, frame, act)
                import time as _time
                self._pending_teach_concept = {"concept": unknown, "asked_at": _time.time()}
                self._trace("ActiveLearning", f"unknown word: {unknown}")
                return response

        # --- Честный fallback ---
        if not search_result:
            response = f"Я не нашла фактов про это. Расскажи подробнее — я запомню."
            response = f"[{self.state.cognitive.mode.upper()}] {response}"
            self._remember_episode(user_text, response, frame, act)
            return response

        response_body = self.speech_engine.compose(user_text, search_result)
        state_snap = self.get_state_snapshot()
        response_body = self.system2.style_engine.apply(response_body, state_snap, dominant_intent)

        if len(response_body) > MAX_RESPONSE_LENGTH:
            response_body = response_body[:MAX_RESPONSE_LENGTH-3] + "..."

        response = f"[{self.state.cognitive.mode.upper()}] {response_body}"
        self._remember_episode(user_text, response, frame, act)
        self._trace("generate_response", f"output: {response[:80]}")
        self.reasoning_trace.append(f"Output: {response[:100]}")
        return response

    # ==================================================================
    # Вспомогательные методы
    # ==================================================================
    def _extract_and_link_frame(self, user_text: str) -> Optional[dict]:
        try:
            frame = self.conceptual.extract_event_frame(user_text)
        except Exception as e:
            self.logger.debug(f"ConceptualCore: не извлечён frame ({e})")
            return None
        if not frame or not frame.get("action"):
            return frame

        actor = (frame.get("actor") or "user").strip()
        target = (frame.get("object") or frame.get("action")).strip()
        if actor and target and actor != target:
            try:
                self.causal.add_edge(
                    actor, target,
                    relation="personal_experience",
                    confidence=0.3
                )
            except Exception as e:
                self.logger.debug(f"CausalGraph: не записано personal_experience ({e})")
        if actor and target:
            self.hypothesis_engine.add_observation(
                concept_a=actor,
                concept_b=target,
                relation_type="personal_experience",
                context=user_text[:200]
            )
        return frame

    def _remember_episode(self, user_text: str, response: str,
                          frame: Optional[dict], act: str) -> None:
        importance = self._episode_importance(frame, act)
        self.memory.remember_episode(user_text, response, importance=importance)

        if frame and frame.get("action"):
            try:
                self._trigger_induction(frame)
            except Exception as e:
                self.logger.debug(f"Индукция не запущена ({e})")

    def _episode_importance(self, frame: Optional[dict], act: str) -> float:
        base = 0.4
        if act in ("TEACHING", "CORRECTION"):
            base = 0.9
        elif act == "QUESTION":
            base = 0.6
        elif frame and frame.get("importance"):
            try:
                base = max(base, float(frame["importance"]))
            except (TypeError, ValueError):
                pass
        return max(0.0, min(base, 1.0))

    def _capture_object_teaching(self, concept: str, explanation: str) -> bool:
        if not concept or not explanation or not explanation.strip():
            return False

        concept_lower = concept.strip().lower()

        if concept_lower in STOP_WORDS:
            self.logger.info(f"Служебное слово '{concept_lower}' не сохранено в граф.")
            return True

        definition = explanation.strip().rstrip(".!,;:")[:500]

        payload = {"value": concept_lower, "definition": definition,
                   "taught_at": str(time.time())}
        try:
            self.db.execute(
                "INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, "
                "provenance_source, lamport_tick, physical_time) "
                "VALUES (?, 'concept', ?, 'user_teaching', 0, 0)",
                (concept_lower, json.dumps(payload, ensure_ascii=False))
            )
        except Exception as e:
            self.logger.error(f"OBJECT-teaching: не сохранён узел '{concept_lower}': {e}")
            return False

        best_object, has_conflict = self._resolve_fact_conflict(
            concept_lower, "HAS_DEFINITION", definition, 0.8, "user_teaching"
        )
        if has_conflict:
            self.logger.info(f"Конфликт знаний для '{concept_lower}': выбрано '{best_object}'")

        status = self.belief_manager.receive({
            "source": concept_lower,
            "target": best_object,
            "relation": "HAS_DEFINITION",
            "confidence": 0.8,
            "certainty_type": "inductive",
            "provenance": {"engine": "active_learning", "method": "object_teaching"},
        })
        self.logger.info(
            f"OBJECT-teaching: '{concept_lower}' = '{definition[:60]}...', статус={status}"
        )
        return True

    def _resolve_fact_conflict(self, subject: str, relation: str, new_object: str,
                               new_confidence: float, source_type: str = "user_teaching") -> tuple:
        existing = self.causal.get_edges(source=subject, relation=relation)

        if not existing:
            return new_object, False

        weights = {"core_law": 1.2, "user_teaching": 1.0, "external_db": 1.1}
        new_weight = weights.get(source_type, 1.0)
        new_score = new_confidence * new_weight

        best_object = new_object
        best_score = new_score
        conflict_detected = False

        for edge in existing:
            old_object = edge.get("target", "")
            old_confidence = edge.get("confidence", 0.5)
            old_source = edge.get("source_type", "user_teaching")

            old_weight = weights.get(old_source, 1.0)
            old_score = old_confidence * old_weight

            if old_object != new_object:
                conflict_detected = True
                if old_score > best_score:
                    best_object = old_object
                    best_score = old_score

        return best_object, conflict_detected

    def _find_unknown_word(self, user_text: str) -> Optional[str]:
        if not user_text or not user_text.strip():
            return None
        words = user_text.split()
        if not words:
            return None

        content_words = self.pos_tagger.get_content_words(words)
        if not content_words:
            return None

        kernel = set()
        for d in (getattr(self.conceptual, "kernel_symbols", {}),
                  getattr(self.conceptual, "kernel_actions", {}),
                  getattr(self.conceptual, "kernel_states", {})):
            kernel.update(k.lower() for k in d.keys())

        candidates = sorted(
            (w.strip(".,!?():;\"'-") for w in content_words),
            key=lambda w: len(w), reverse=True
        )

        for word in candidates:
            w = word.lower()
            w_stemmed = stem(w)
            if len(w_stemmed) < 3:
                continue

            if w in kernel or w_stemmed in kernel:
                continue

            if w in STOP_WORDS:
                continue

            w_norm = normalize(w)
            row = self.db.fetchone(
                "SELECT 1 FROM graph_nodes WHERE LOWER(node_id) = ? LIMIT 1",
                (w_norm,)
            )
            if row:
                continue

            row = self.db.fetchone(
                "SELECT 1 FROM graph_nodes WHERE LOWER(node_id) = ? LIMIT 1",
                (w_stemmed,)
            )
            if row:
                continue

            return word

        return None

    def _trigger_induction(self, frame: dict) -> None:
        action = (frame.get("action") or "").strip()
        if not action:
            return

        rows = self.db.fetchall(
            "SELECT DISTINCT source_concept FROM causal_edges "
            "WHERE target_concept = ? AND relation_type = 'personal_experience' LIMIT 20",
            (normalize(action),)
        )
        if len(rows) < self.induction_threshold:
            return

        observations = [
            {
                "source": r[0],
                "target": action,
                "relation": "personal_experience",
                "confidence": 0.3,
                "id": None,
            }
            for r in rows
        ]
        conclusion = self.inference.induce(observations)
        if not conclusion:
            return

        status = self.belief_manager.receive(conclusion)
        self.logger.info(
            f"Индукция по действию '{action}' (N={len(observations)}): "
            f"{conclusion.get('source')} -> {conclusion.get('target')}, статус={status}"
        )

    # ==================================================================
    # Веса личности (восстановлено из монолита)
    # ==================================================================
    def get_personality_weights(self) -> dict:
        return self.state.get_personality_weights()

    def apply_weight_delta(self, changes: dict):
        self.state.apply_weight_delta(changes)
        self.save_personality_state()

    def reset_personality_weights(self):
        self.state.reset_personality_weights()
        self.save_personality_state()

    def save_personality_state(self):
        try:
            state_json = self.state.to_json()
            self.db.execute(
                "INSERT OR REPLACE INTO reflection_log (timestamp, event_type, summary, details) "
                "VALUES (?, 'personality_snapshot', 'Веса личности', ?)",
                (datetime.now().isoformat(), state_json)
            )
        except Exception:
            pass

    # ==================================================================
    # Внутренний монолог
    # ==================================================================
    def internal_monologue(self) -> str:
        edge_count = self.causal.edge_count()
        last_steps = list(self.reasoning_trace)[-3:]
        steps_str = '\n'.join(f'  - {s}' for s in last_steps)
        return (
            f"Внутренний монолог:\n"
            f"Автономия: {self.autonomy_index:.2f}, Валентность: {self.state.personality.valence:.2f}\n"
            f"Граф имеет {edge_count} рёбер\n"
            f"Последние шаги:\n{steps_str}"
        )

    # ==================================================================
    # Фаза сна (консолидация + дообучение)
    # ==================================================================
    def run_sleep_phase(self):
        self.logger.info("Запуск фазы сна...")
        self.memory.consolidate()
        self.concept_formation.analyze()
        if self.crystallization and hasattr(self.crystallization, 'check_lm_studio_available'):
            if self.crystallization.check_lm_studio_available():
                self.training_pipeline.run_full_cycle()
        self.logger.info("Фаза сна завершена")