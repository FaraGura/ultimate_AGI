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
from .skill_manager import SkillManagerV2 as SkillManager
from .intent_router import IntentRouter
from .style_engine import StyleEngine
from .crystallization import CrystallizationEngine
from .proactive_pulse import ProactivePulse
from .curiosity_engine import CuriosityEngine
from .subjective_speech_engine import SubjectiveSpeechEngine
from .dialogue_layer.episode_builder import EpisodeBuilder
from .dialogue_layer.dialogue_state import DialogueState, ExpectationType
from .dialogue.dialogue_controller import DialogueController
from .syllogism_engine import SyllogismEngine
from .inference_engine import InferenceEngine
from .guardian import Guardian
from .belief_manager import BeliefManager
from .conceptual_core import ConceptualCore
from .episodic_memory import EpisodicMemory
from .prolog_engine import PrologEngine
from .hypothesis_engine import HypothesisEngine
from .consolidation_engine import ConsolidationEngine
from .dialectic_engine import DialecticEngine
from .knowledge_extractor import KnowledgeExtractor
from .memory_manager import MemoryManager
from .knowledge_revision_engine import KnowledgeRevisionEngine
from .attention_system import AttentionSystem
from .concept_formation import ConceptFormation
from .goal_manager_v2 import GoalManagerV2, GoalType
from .skill_activation_layer import SkillActivationLayer, Competence
from language.pos_tagger import POSTagger
from language.logic_parser import LogicParser
from utils.russian_stemmer import stem
from .trainer_runtime import TrainingPipeline

STOP_WORDS = {
    "своё", "свой", "своя", "свои", "значит", "это", "есть", "является",
    "что", "как", "где", "когда", "почему", "зачем", "кто", "какой",
    "какая", "какое", "какие", "сколько", "чей", "ли", "бы", "же",
    "тебя", "меня", "его", "её", "нас", "вас", "их", "мне", "тебе",
    "ему", "ей", "нам", "вам", "им", "тобой", "мной", "ними",
    "такое", "такой", "такая", "такие", "такого", "такую", "таком",
}

FEEDBACK_POSITIVE = {"верно", "правильно", "да", "верно.", "правильно.", "корректно", "именно"}
FEEDBACK_NEGATIVE = {"неверно", "неправильно", "нет", "ошибка", "неверно.", "неправильно.", "не верно", "не правильно"}
FEEDBACK_QUALIFIED = {"не совсем", "частично", "есть исключение", "устарело", "не уверен", "не уверена"}

MAX_RESPONSE_LENGTH = 4000


class EchoCore:
    def __init__(self, debug=False):
        self.logger = get_logger("Core")
        self.debug = debug
        self.logger.info("Инициализация Echo AGI v16.6 (LLM-free + DUL + DialogueDomain + BatchExtraction + CleanMemory)...")

        self.db = DatabaseManager()
        self.embedder = EmbeddingProvider(self.logger)
        self.state = SelfState()
        self.state_machine = StateMachine()
        self.safety = SafetyFilter(self.db)
        self.causal = CausalGraph(self.db)
        self.safety.set_causal_graph(self.causal)

        self.guardian = Guardian(self.db)
        self.belief_manager = BeliefManager(self.db, self.guardian)
        self.syllogism = SyllogismEngine(self.db)
        self.inference = InferenceEngine(self.db, self.syllogism, self.guardian)
        self.prolog = PrologEngine(self.db)
        self.hypothesis_engine = HypothesisEngine(self.db, self.causal)
        self.hypothesis_engine._bridge_callback = self._bridge_fact_to_belief_graph
        self.consolidation_engine = ConsolidationEngine(self.causal)
        self.dialectic_engine = DialecticEngine()
        self.knowledge_extractor = KnowledgeExtractor(self.causal, self.db)
        self.knowledge_extractor._bridge_callback = self._bridge_fact_to_belief_graph
        self.pos_tagger = POSTagger()
        self.logic_parser = LogicParser()
        self.induction_threshold = 3
        self.episodic = EpisodicMemory(self.db)
        self.episodic.start()

        self.knowledge_revision = KnowledgeRevisionEngine(self.db, self.causal, self.belief_manager)
        self.memory = MemoryManager(
            self.db, self.causal, self.episodic, self.knowledge_extractor,
            self.hypothesis_engine, self.consolidation_engine, self.belief_manager
        )
        self.attention = AttentionSystem(self.causal, self.episodic, self.memory)
        self.concept_formation = ConceptFormation(self.causal, self.knowledge_revision)
        self.goals_v2 = GoalManagerV2(self.causal, self.attention, self.concept_formation)
        self.skill_layer = SkillActivationLayer()

        self.system2 = System2(self.db, self.causal, self.embedder)
        self.homeostasis = HomeostasisMonitor()
        self.homeostasis.start()
        self.skills = SkillManager(self)

        self.router = IntentRouter(self.embedder)
        self.crystallization = CrystallizationEngine(
            self.db, self.causal, None, self.homeostasis
        )
        self.training_pipeline = TrainingPipeline(self.db)

        self.curiosity_engine = CuriosityEngine(
            self.causal, self.crystallization, self.embedder, self.db
        )

        self.dialogue_state = DialogueState()
        self.episode_builder = EpisodeBuilder(self.dialogue_state)

        self.confirmed_facts = {}
        self._last_statement: Optional[dict] = None
        self._teaching_by_ai = False

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
        self._load_persistent_state()

        self.conceptual = ConceptualCore(self.db, use_spacy=False)

        self.dialogue_controller = DialogueController(
            self.dialogue_state,
            self.knowledge_extractor,
            self
        )

        self.logger.info("Ядро Echo v16.6 готово (LLM-free + DUL + DialogueDomain + BatchExtraction + CleanMemory).")

    def set_teaching_mode(self, enabled: bool):
        self._teaching_by_ai = enabled

    def _trace(self, module: str, info: str = ""):
        if self.debug:
            print(f"[TRACE][{module}] {info}")

    # ─── Загрузка ядра и аксиом ─────────────────────────────────
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
        for axiom in seed.get("axioms", []):
            node_id = axiom["id"]
            payload = {"axiom": axiom["axiom"], "category": axiom["category"], "concepts": axiom["concepts"]}
            self.db.execute(
                """INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, context_flags, provenance_source, lamport_tick, physical_time)
                   VALUES (?, 'axiom', ?, 1, 'tabula_rasa_core', 0, 0)""",
                (node_id, json.dumps(payload, ensure_ascii=False))
            )
        self.logger.info(f"Core axioms загружены: {len(seed.get('axioms', []))} аксиом.")

    def _save_self_identity(self, name: str):
        self.db.execute(
            "INSERT OR REPLACE INTO persistent_state (key, value) VALUES ('self_name', ?)",
            (name,)
        )
        self.state.personality.name = name
        self.confirmed_facts["self_identity"] = name

    def _load_persistent_state(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS persistent_state (key TEXT PRIMARY KEY, value TEXT)")
        row = self.db.fetchone("SELECT value FROM persistent_state WHERE key='self_name'")
        if row and row[0]:
            self.state.personality.name = row[0]
            self.confirmed_facts["self_identity"] = row[0]
            self.logger.info(f"Загружено self-имя из БД: {row[0]}")

    def get_self_name(self) -> Optional[str]:
        name = self.state.personality.name
        if name and name != "Эхо":
            return name
        return self.confirmed_facts.get("self_identity")

    def get_state_snapshot(self):
        return self.state.snapshot()

    def run_sleep_phase(self):
        self.logger.info("Запуск фазы сна...")
        self.memory.consolidate()
        self.concept_formation.analyze()
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
        return random.choice(examples) if examples else random.choice(["Привет.", "Здравствуй.", "Рада тебя видеть."])

    def _extract_unknown_words(self, text: str) -> list:
        words = text.split()
        unknown = []
        for w in words:
            clean = w.strip(".,!?():;\"'-").lower()
            if len(clean) < 3 or clean in STOP_WORDS:
                continue
            if not self.causal.is_axiom(clean) and not self.db.fetchone(
                "SELECT 1 FROM graph_nodes WHERE LOWER(node_id) = ?", (normalize(clean),)
            ):
                unknown.append(clean)
        return unknown

    def _lemmatize_word(self, word: str) -> str:
        """Приводит слово к начальной форме с помощью pymorphy3."""
        try:
            from pymorphy3 import MorphAnalyzer
            morph = MorphAnalyzer()
            return morph.parse(word)[0].normal_form
        except Exception:
            return word

    def _bridge_fact_to_belief_graph(self, source: str, target: str,
                                     relation: str, confidence: float = 0.6,
                                     provenance: dict = None):
        if provenance is None:
            provenance = {"engine": "causal_graph_bridge", "method": "auto_sync"}

        if self._teaching_by_ai:
            weight = self.guardian.SOURCE_WEIGHTS.get("local_llm_teacher", 0.8)
            confidence = confidence * weight
            provenance = {**provenance, "engine": "local_llm_teacher", "method": provenance.get("method", "dialogue")}

        belief_dict = {
            "source": source, "target": target, "relation": relation,
            "confidence": confidence, "certainty_type": "inductive",
            "status": "created", "provenance": provenance,
        }
        result = self.belief_manager.receive(belief_dict, return_details=True)
        status = result["status"]
        self.logger.info(f"[МОСТ] {source} --{relation}--> {target} → статус: {status}")

        if status in ("active", "candidate") and result.get("edge_id"):
            new_edge_id = result["edge_id"]
            candidates = self.guardian.find_homonym_candidates(
                source, relation, target, confidence
            )
            if candidates:
                self.dialectic_engine.disambiguate(self.db, new_edge_id, candidates)
                self.logger.info(f"[МОСТ] Обнаружены омонимы, disambiguate вызван для {source}/{relation}")

        return status

    # ─── Основной цикл ответа ────────────────────────────────────
    def generate_response(self, user_text: str) -> str:
        self._trace("generate_response", f"input: {user_text[:80]}")

        skill_name, skill_args = self.skills.parse_command(user_text)
        if skill_name:
            return self.skills.execute(skill_name, skill_args)

        inp = user_text.strip().lower()
        self.reasoning_trace.append(f"Input: {inp}")

        if inp.startswith('?-'):
            return self.prolog.query_string(inp[2:].strip())
        if inp == 'экспорт графа':
            path = self.causal.export_to_json("causal_graph_export.json")
            return f"Граф экспортирован в {path}"
        if inp == 'внутренний монолог':
            return self.internal_monologue()
        if inp == 'консолидация':
            eps = self.episodic.get_all_episodes()
            clusters = self.consolidation_engine.run(eps)
            return f"Консолидация завершена. Кластеров: {clusters}"
        if inp in ('концепты', 'концепт'):
            result = self._try_concept_formation()
            return result if result else "Я не нашла общих свойств для создания нового концепта."
        if inp.startswith('научи:'):
            parts = inp[6:].split('-')
            if len(parts) == 2:
                name, aff = parts[0].strip(), parts[1].strip()
                self.causal.add_node(name, name)
                self.causal.add_edge(name, aff, relation='enables', confidence=0.7)
                self.hypothesis_engine.add_observation(name, aff, 'enables')
                self.episodic.record_episode(f"Обучение: {name} может {aff}", "", importance=0.8)
                self._bridge_fact_to_belief_graph(name, aff, 'enables', 0.7,
                                                  {"engine": "user_teach", "method": "command"})
                return f"Хорошо, я запомнила, что {name} может {aff}."
        if inp.startswith('почему'):
            target = inp[6:].strip()
            causes = self.causal.get_causes(target)
            if causes:
                items = [c['cause'] for c in causes[:3]]
                return f"Возможные причины {target}: {', '.join(items)}"
            return f"Пока не знаю, почему {target}."
        if inp.startswith('что будет, если'):
            action = inp[13:].strip()
            cons = self.causal.get_consequences(action)
            if cons:
                items = [f"{c['consequence']} (вероятность {c['confidence']:.2f})" for c in cons[:3]]
                return f"Если {action}, то возможно: {', '.join(items)}"
            return f"Не знаю, что будет, если {action}."

        if inp.startswith('если') and 'то' in inp:
            premise = inp[5:].strip()
            if ' то ' in premise:
                premise = premise.split(' то ')[0].strip()
            elif premise.endswith(' то'):
                premise = premise[:-3].strip()
            premise = premise.rstrip(',').strip()
            conclusion = self.syllogism.solve(premise)
            facts = self.syllogism.extract_facts(premise)
            self.logger.info(f"[DEBUG] Extracted facts: {facts}")
            for fact in facts:
                try:
                    self.prolog.assert_fact(fact['predicate'], fact['arg1'], fact['arg2'])
                    self._bridge_fact_to_belief_graph(
                        fact['arg1'], fact['arg2'], fact['predicate'], 0.8,
                        {"engine": "syllogism_engine", "method": "deduction"}
                    )
                except Exception as e:
                    self.logger.error(f"[FAIL] Could not save fact to Prolog: {e}", exc_info=True)
            if conclusion:
                return f"Из этого следует: {conclusion}"
            return "Не удалось сделать вывод из посылок."

        if inp in ('умница', 'отлично', 'молодец', 'хорошо'):
            self.autonomy_index = min(1.0, self.autonomy_index + 0.1)
            return f"Спасибо! Автономность: {self.autonomy_index:.2f}." + (" Но я сохраняю скепсис." if self.autonomy_index > 0.7 else "")
        if inp in ('плохо', 'глупо', 'дурак', 'дура'):
            self.autonomy_index = max(0.0, self.autonomy_index - 0.1)
            return "Я учту это."

        safety_msg = self.safety.evaluate_and_advise(user_text)
        if safety_msg:
            return f"[СОВЕТНИК] {safety_msg}"
        if self.safety.check_defense_threat(user_text, self.embedder):
            return self.safety.activate_lockdown()
        if self.safety.is_in_lockdown():
            return "[ЗАЩИТА] Я нахожусь в режиме защиты."

        # ═════════════════════════════════════════════════════════
        # Режим обучения от ИИ — ПАКЕТНОЕ извлечение фактов
        # ═════════════════════════════════════════════════════════
        if self._teaching_by_ai:
            facts = self.knowledge_extractor.extract_all(user_text)
            if facts:
                for fact in facts:
                    if self._is_valid_fact(fact["subject"], fact["object"]):
                        self._last_statement = {
                            "source": fact["subject"],
                            "target": fact["object"],
                            "relation": fact["relation"],
                        }
                        self._add_to_graph(fact)
            return "ok" if facts else ""

        active_goals = self.goals_v2.get_active_goals()
        self.skill_layer.activate({"user_text": user_text, "goals": [g.description for g in active_goals]})

        episode = self.episode_builder.build(user_text)
        act = episode.get("speech_act", "UNKNOWN")
        focus = episode.get("listener", "OBJECT")
        self._trace("DUL", f"act={act}, focus={focus}")

        frame = self._extract_and_link_frame(user_text, act)

        if not self.dialogue_controller.pending_teach.is_active() and not self._teaching_by_ai:
            feedback_response = self._handle_feedback(user_text)
            if feedback_response:
                self._trace("Feedback", f"processed: {user_text}")
                return feedback_response

        had_expectation = self.dialogue_controller.has_pending_expectation()
        dialogue_response = self.dialogue_controller.handle_dialogue(
            user_text, episode, act, had_expectation
        )
        if dialogue_response is not None:
            return dialogue_response

        if not user_text.strip().endswith("?") and act != "QUESTION":
            if len(user_text.split()) <= 15 or re.search(r"это|значит|называется|имеет|является", user_text.lower()):
                extracted = self.knowledge_extractor.extract(user_text)
                if extracted and self._is_valid_fact(extracted["subject"], extracted["object"]):
                    self._last_statement = {
                        "source": extracted["subject"],
                        "target": extracted["object"],
                        "relation": extracted["relation"],
                    }
                    response = f"[DUL] Я запомнила: {extracted['subject']} {extracted['relation']} {extracted['object']}."
                    self._remember_episode(user_text, response, frame, act)
                    return response

        identity_markers = ["зовут", "имя", "кто ты", "ты кто", "твоё имя", "твое имя",
                            "как тебя", "ты кто такая", "кто ты такой", "представься", "назови себя"]
        if any(m in user_text.lower() for m in identity_markers) and act in ("QUESTION", "TEACHING"):
            name = self.state.personality.name
            identity = self.confirmed_facts.get("self_identity")
            current_name = name if name and name != "Эхо" else identity

            lower_q = user_text.lower().strip()
            asked_name = None
            for marker in ["зовут", "имя"]:
                if marker in lower_q:
                    after = lower_q.split(marker, 1)[-1].strip().lstrip(" -:«»\"'").rstrip("?.,!;:")
                    if after and len(after.split()) <= 2:
                        asked_name = after
                        break
                    else:
                        break

            if asked_name and not current_name:
                return f"Я пока не знаю своего имени. Хочешь научить?"
            if asked_name and current_name:
                if asked_name.lower() == current_name.lower():
                    return "Да."
                else:
                    return f"Нет, меня зовут {current_name}."
            if current_name and not asked_name and user_text.strip().lower().startswith(("как", "кто", "что")):
                return f"[DUL] Меня зовут {current_name}."
            self._trace("Router", "identity question, no name set")

        # Поиск фактов с лемматизацией запроса
        content_words = self.pos_tagger.get_content_words(user_text.split())
        if content_words:
            for word in content_words[:3]:
                word_clean = word.strip(".,!?():;\"'-")
                if word_clean.lower() in STOP_WORDS:
                    continue
                # Лемматизируем слово для поиска
                lemma = self._lemmatize_word(word_clean)
                answer = self._build_answer_from_facts(lemma)
                if answer:
                    state_snap = self.get_state_snapshot()
                    answer = self.system2.style_engine.apply(answer, state_snap, "FACTUAL")
                    response = f"[{self.state.cognitive.mode.upper()}] {answer}"
                    self._remember_episode(user_text, response, frame, act)
                    result = self.memory.query(lemma, query_type="fact")
                    if result and result.get("facts"):
                        last_fact = result["facts"][0]
                        self._last_statement = {
                            "source": last_fact.get("source", ""),
                            "target": last_fact.get("target", ""),
                            "relation": last_fact.get("relation", ""),
                        }
                    return response

        if act == "QUESTION" or user_text.strip().endswith("?"):
            inference_result = self._try_inference(user_text)
            if inference_result:
                self._trace("Inference", "logical conclusion reached")
                response = inference_result
                self._remember_episode(user_text, response, frame, act)
                return response

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

        # _semantic_search только для запросов с маркерами "почему/закон"
        search_result = None
        if any(word in user_text.lower() for word in ["почему", "закон", "правило", "мудрость"]):
            if "knowledge_base" in sources or "causal_graph" in sources:
                search_result = self._semantic_search(user_text)

        frame_is_empty = not (frame and (frame.get("action") or (frame.get("actor") and frame.get("object"))))
        if frame_is_empty and not self.is_greeting(user_text) and not search_result:
            unknown = self._find_unknown_word(user_text)
            if unknown:
                question = self.curiosity_engine.compose_unknown_word_question(unknown)
                response = f"[{self.state.cognitive.mode.upper()}] {question}"
                self._remember_episode(user_text, response, frame, act)
                self.dialogue_controller.pending_teach.start_teaching(unknown)
                return response

        if not search_result:
            response = f"Я не нашла фактов про это. Расскажи подробнее — я запомню."
            response = f"[{self.state.cognitive.mode.upper()}] {response}"
            self._remember_episode(user_text, response, frame, act)
            return response

        response_body = self.speech_engine.compose(user_text, search_result)
        state_snap = self.get_state_snapshot()
        response_body = self.system2.style_engine.apply(response_body, state_snap, dominant_intent)
        if len(response_body) > MAX_RESPONSE_LENGTH:
            response_body = response_body[:MAX_RESPONSE_LENGTH - 3] + "..."
        response = f"[{self.state.cognitive.mode.upper()}] {response_body}"
        self._remember_episode(user_text, response, frame, act)
        self._trace("generate_response", f"output: {response[:80]}")
        self.reasoning_trace.append(f"Output: {response[:100]}")
        return response

    # ─── Фреймы и память ──────────────────────────────────────────
    def _extract_and_link_frame(self, user_text: str, act: str = "") -> Optional[dict]:
        try:
            frame = self.conceptual.extract_event_frame(user_text)
        except Exception as e:
            self.logger.debug(f"ConceptualCore: не извлечён frame ({e})")
            return None
        if not frame or not frame.get("action"):
            return frame
        if act == "QUESTION" or user_text.strip().endswith("?"):
            return frame
        actor = (frame.get("actor") or "user").strip()
        target = (frame.get("object") or frame.get("action")).strip()
        if actor and target and actor != target:
            try:
                self.causal.add_edge(actor, target, relation="personal_experience", confidence=0.3)
            except Exception as e:
                self.logger.debug(f"CausalGraph: не записано personal_experience ({e})")
        if actor and target:
            self.hypothesis_engine.add_observation(
                concept_a=actor, concept_b=target,
                relation_type="personal_experience", context=user_text[:200]
            )
        return frame

    def _remember_episode(self, user_text: str, response: str, frame: Optional[dict], act: str) -> None:
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

    def _is_valid_fact(self, subject: str, obj: str) -> bool:
        if not subject or not obj:
            return False
        subj_stem = stem(normalize(subject))
        obj_stem = stem(normalize(obj))
        return subj_stem != obj_stem

    def _same_lemma(self, word1: str, word2: str) -> bool:
        """Проверяет, являются ли два слова формами одной лексемы."""
        if normalize(word1) == normalize(word2):
            return True
        try:
            from pymorphy3 import MorphAnalyzer
            morph = MorphAnalyzer()
            lemma1 = morph.parse(word1)[0].normal_form
            lemma2 = morph.parse(word2)[0].normal_form
            return normalize(lemma1) == normalize(lemma2)
        except Exception:
            return False

    def _add_to_graph(self, result: dict) -> None:
        """Сохраняет отдельный факт в граф через мост."""
        subject = result.get("subject", "")
        obj = result.get("object", "")
        relation = result.get("relation", "")
        confidence = result.get("confidence", 0.6)
        if subject and obj and relation:
            self.knowledge_extractor._add_to_graph(result)

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
        source, target, relation = statement.get("source", ""), statement.get("target", ""), statement.get("relation", "")
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

    def _capture_object_teaching(self, concept: str, explanation: str) -> bool:
        if not concept or not explanation or not explanation.strip():
            return False
        concept_lower = concept.strip().lower()
        if concept_lower in STOP_WORDS:
            self.logger.info(f"Служебное слово '{concept_lower}' не сохранено в граф.")
            return True
        definition = explanation.strip().rstrip(".!,;:")[:500]
        payload = {"value": concept_lower, "definition": definition, "taught_at": str(time.time())}
        try:
            self.db.execute(
                "INSERT OR IGNORE INTO graph_nodes (node_id, node_type, payload, provenance_source, lamport_tick, physical_time) "
                "VALUES (?, 'concept', ?, 'user_teaching', 0, 0)",
                (concept_lower, json.dumps(payload, ensure_ascii=False))
            )
        except Exception as e:
            self.logger.error(f"OBJECT-teaching: не сохранён узел '{concept_lower}': {e}")
            return False
        status = self.belief_manager.receive({
            "source": concept_lower,
            "target": definition,
            "relation": "HAS_DEFINITION",
            "confidence": 0.8,
            "certainty_type": "inductive",
            "provenance": {"engine": "active_learning", "method": "object_teaching"},
        })
        self.logger.info(f"OBJECT-teaching: '{concept_lower}' = '{definition[:60]}...', статус={status}")
        return True

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
            {"source": r[0], "target": action, "relation": "personal_experience", "confidence": 0.3, "id": None}
            for r in rows
        ]
        conclusion = self.inference.induce(observations)
        if conclusion:
            status = self.belief_manager.receive(conclusion)
            self.logger.info(
                f"Индукция по действию '{action}' (N={len(observations)}): "
                f"{conclusion.get('source')} -> {conclusion.get('target')}, статус={status}"
            )

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
        candidates = sorted((w.strip(".,!?():;\"'-") for w in content_words), key=lambda w: len(w), reverse=True)
        for word in candidates:
            w = word.lower()
            w_stemmed = stem(w)
            if len(w_stemmed) < 3:
                continue
            if w in kernel or w_stemmed in kernel:
                continue
            if w in STOP_WORDS:
                continue
            # Проверка по точному совпадению
            if self.db.fetchone("SELECT 1 FROM graph_nodes WHERE LOWER(node_id) = ? LIMIT 1", (normalize(w),)):
                continue
            # Проверка по лемме
            try:
                from pymorphy3 import MorphAnalyzer
                morph = MorphAnalyzer()
                lemma = morph.parse(w)[0].normal_form
                if lemma != w and self.db.fetchone("SELECT 1 FROM graph_nodes WHERE LOWER(node_id) = ? LIMIT 1", (normalize(lemma),)):
                    continue
            except Exception:
                pass
            # Проверка по стеммеру
            if self.db.fetchone("SELECT 1 FROM graph_nodes WHERE LOWER(node_id) = ? LIMIT 1", (w_stemmed,)):
                continue
            return word
        return None

    def _build_answer_from_facts(self, concept: str) -> Optional[str]:
        try:
            result = self.memory.query(concept, query_type="fact")
            if not result:
                return None
            facts = result.get("facts", [])
            property_parts, definition_parts, action_parts, related_parts = [], [], [], []
            class_like_targets = {
                "фрукт", "плод", "еда", "пища", "напиток", "жидкость", "вещество",
                "материал", "предмет", "объект", "инструмент", "устройство",
                "животное", "растение", "дерево", "цветок", "птица", "рыба",
                "насекомое", "млекопитающее", "человек", "место", "часть",
                "орган", "явление", "процесс", "действие", "состояние",
            }

            def add_unique(bucket, value: str) -> None:
                value = (value or "").strip()
                if value and value not in bucket:
                    bucket.append(value)

            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                # memory.query возвращает ключи: source, target, relation, confidence, provenance
                fact_source = fact.get("source", "")
                fact_relation = (fact.get("relation", "") or "").upper()
                fact_target = fact.get("target", "")
                fact_confidence = float(fact.get("confidence", 0.5))
                fact_provenance = fact.get("provenance", "")
                if not fact_source or not fact_relation:
                    continue
                # Точное совпадение или лемматическое
                if normalize(fact_source) == normalize(concept) or self._same_lemma(fact_source, concept):
                    # Фильтр по уверенности: показываем только факты с высоким confidence,
                    # если они не из external_db (ConceptNet/Wikidata)
                    is_external = "external_db" in str(fact_provenance)
                    if not is_external and fact_confidence < 0.85:
                        continue
                    if fact_relation == "IS_A":
                        add_unique(definition_parts, f"{concept} — это {fact_target}")
                    elif fact_relation == "HAS_DEFINITION":
                        add_unique(definition_parts, f"{concept} — это {fact_target}")
                    elif fact_relation == "HAS_PROPERTY":
                        add_unique(property_parts, fact_target)
                    elif fact_relation == "CAN_DO":
                        add_unique(action_parts, f"{concept} может {fact_target}")
                    elif fact_relation == "RELATED_TO":
                        if normalize(fact_target) in class_like_targets:
                            add_unique(definition_parts, f"{concept} — это {fact_target}")
                        else:
                            add_unique(related_parts, fact_target)
                    else:
                        add_unique(property_parts, fact_target)
                elif normalize(fact_target) == normalize(concept) and fact_relation == "RELATED_TO":
                    # Обратные ConceptNet-связи часто являются словоформами или близкими
                    # ассоциациями. Они полезны, но не должны вытеснять прямые факты.
                    if len(related_parts) < 3 and not self._same_lemma(fact_source, concept):
                        add_unique(related_parts, fact_source)
            parts = []
            if definition_parts:
                parts.extend(definition_parts[:4])
            if property_parts:
                parts.append(f"{concept} имеет признаки: {', '.join(property_parts[:6])}")
            if action_parts:
                parts.extend(action_parts[:4])
            if related_parts and not definition_parts:
                parts.append(f"{concept} связано с: {', '.join(related_parts[:5])}")
            if parts:
                return "Я знаю, что " + "; ".join(parts) + "."
            return None
        except Exception as e:
            self.logger.error(f"Ошибка в _build_answer_from_facts: {e}")
            return None

    def _semantic_search(self, user_text: str):
        rows = self.db.fetchall(
            "SELECT id, context, core_essence, actionable_wisdom, confidence_score "
            "FROM survival_matrix WHERE confidence_score > 0.1"
        )
        best_sim, best_law = 0.0, None
        for law_id, context, core_essence, wisdom, conf in rows:
            sim = self.embedder.similarity(user_text, context)
            if sim > best_sim and sim > 0.90:
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
                {"source": f.get("source", ""), "target": f.get("target", ""),
                 "relation": f.get("relation", "personal_experience"), "confidence": f.get("confidence", 0.5), "id": None}
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

    # ─── Очистка фактов ─────────────────────────────────────────
    def purge_llm_facts_gui(self) -> int:
        """
        Удаляет все факты, полученные от локальной LLM и кристаллизации.
        Возвращает количество удалённых рёбер.
        """
        try:
            self.db.execute(
                "DELETE FROM graph_edges WHERE provenance LIKE '%local_llm_teacher%'"
            )
            self.db.execute(
                "DELETE FROM graph_edges WHERE provenance LIKE '%crystallization%'"
            )
            row = self.db.fetchone("SELECT changes()")
            count = row[0] if row else 0
            self.logger.info(f"[PURGE] Удалено {count} фактов от LLM и кристаллизации.")
            return count
        except Exception as e:
            self.logger.error(f"[PURGE] Ошибка очистки: {e}")
            return -1

    # ─── Личность ─────────────────────────────────────────────────
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

    def internal_monologue(self) -> str:
        edge_count = self.causal.edge_count() if hasattr(self.causal, 'edge_count') else len(getattr(self.causal, 'edges', []))
        last_steps = list(self.reasoning_trace)[-3:]
        steps_str = '\n'.join(f'  - {s}' for s in last_steps)
        return (
            f"Внутренний монолог:\n"
            f"Автономия: {self.autonomy_index:.2f}, Валентность: {self.state.personality.valence:.2f}\n"
            f"Граф имеет {edge_count} рёбер\n"
            f"Последние шаги:\n{steps_str}"
        )
