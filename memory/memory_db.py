# memory/memory_db.py
import sqlite3
import threading
from echo_core.config import DATABASE_FILE
from utils.utils_logger import get_logger

class DatabaseManager:
    def __init__(self):
        self.logger = get_logger("DB")
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        tables = [
            '''CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_text TEXT, answer TEXT, weight REAL, uses INTEGER, created TEXT)''',
            '''CREATE TABLE IF NOT EXISTS survival_matrix (id INTEGER PRIMARY KEY AUTOINCREMENT, context TEXT UNIQUE, core_essence TEXT, blind_spots TEXT, actionable_wisdom TEXT, confidence_score REAL DEFAULT 1.0, failure_exceptions TEXT DEFAULT '[]', tags TEXT DEFAULT '[]', reflex_level INTEGER DEFAULT 0, created TEXT)''',
            '''CREATE TABLE IF NOT EXISTS learned_knowledge (id INTEGER PRIMARY KEY AUTOINCREMENT, knowledge_type TEXT, category TEXT, content TEXT, context TEXT, weight REAL, uses INTEGER, created TEXT)''',
            '''CREATE TABLE IF NOT EXISTS risk_flags (id INTEGER PRIMARY KEY AUTOINCREMENT, topic_key TEXT, risk_level TEXT, priority REAL, trigger_phrase TEXT, context TEXT, warned INTEGER DEFAULT 0, created TEXT)''',
            '''CREATE TABLE IF NOT EXISTS concept_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, concept TEXT UNIQUE NOT NULL, surface_truth TEXT, paradoxes TEXT DEFAULT '[]', questions TEXT DEFAULT '[]', confidence REAL DEFAULT 0.8, last_used TEXT DEFAULT CURRENT_TIMESTAMP, parent_law_id INTEGER, semantic_hash TEXT, sensor_types TEXT DEFAULT '["text"]', FOREIGN KEY (parent_law_id) REFERENCES survival_matrix(id) ON DELETE SET NULL)''',
            '''CREATE TABLE IF NOT EXISTS reflection_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, event_type TEXT, summary TEXT, details TEXT)''',
            '''CREATE TABLE IF NOT EXISTS causal_edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source_concept TEXT NOT NULL, target_concept TEXT NOT NULL, relation_type TEXT NOT NULL, confidence REAL DEFAULT 0.5, evidence_count INTEGER DEFAULT 0, last_updated TEXT, UNIQUE(source_concept, target_concept, relation_type))''',
            '''CREATE TABLE IF NOT EXISTS graph_nodes (node_id TEXT PRIMARY KEY, node_type TEXT NOT NULL, payload BLOB, context_flags INTEGER DEFAULT 1, provenance_source TEXT DEFAULT 'tabula_rasa', lamport_tick INTEGER DEFAULT 0, physical_time INTEGER DEFAULT 0, origin_instance_id TEXT, parent_node_id TEXT, created_by_module TEXT, payload_schema_hash TEXT, semantic_signature TEXT)''',
            '''CREATE TABLE IF NOT EXISTS graph_edges (edge_id TEXT PRIMARY KEY, source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation_type TEXT NOT NULL, context_flags INTEGER DEFAULT 1, provenance_source TEXT DEFAULT 'tabula_rasa', confidence_score REAL DEFAULT 1.0, lamport_tick INTEGER DEFAULT 0, physical_time INTEGER DEFAULT 0, origin_instance_id TEXT, parent_node_id TEXT, created_by_module TEXT, FOREIGN KEY (source_node_id) REFERENCES graph_nodes(node_id), FOREIGN KEY (target_node_id) REFERENCES graph_nodes(node_id))''',
            '''CREATE TABLE IF NOT EXISTS graph_conflicts (id INTEGER PRIMARY KEY AUTOINCREMENT, belief_a_id INTEGER, belief_b_id INTEGER, conflict_type TEXT, resolution_status TEXT DEFAULT 'pending')''',
            '''CREATE TABLE IF NOT EXISTS episodic_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_text TEXT,
                echo_response TEXT,
                weight REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                importance REAL DEFAULT 0.5,
                consolidated_to_id INTEGER,
                created TEXT
            )''',
        ]
        for sql in tables:
            cur.execute(sql)

        # Миграция: добавляем новые столбцы, если их нет (до создания индексов!)
        new_columns = {
            'graph_edges': [
                ('status', 'TEXT DEFAULT "active"'),
                ('certainty_type', 'TEXT DEFAULT "deductive"'),
                ('quantifier', 'TEXT DEFAULT "all"'),
                ('provenance', 'TEXT'),
                ('context_flags_json', 'TEXT'),
            ]
        }
        for table, columns in new_columns.items():
            for col_name, col_def in columns:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    self.logger.info(f"Добавлен столбец {table}.{col_name}")
                except sqlite3.OperationalError:
                    pass  # столбец уже существует

        # Индексы
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_concept_name ON concept_nodes(concept)',
            'CREATE INDEX IF NOT EXISTS idx_concept_parent ON concept_nodes(parent_law_id)',
            'CREATE INDEX IF NOT EXISTS idx_concept_hash ON concept_nodes(semantic_hash)',
            'CREATE INDEX IF NOT EXISTS idx_causal_source ON causal_edges(source_concept)',
            'CREATE INDEX IF NOT EXISTS idx_causal_target ON causal_edges(target_concept)',
            'CREATE INDEX IF NOT EXISTS idx_edges_status ON graph_edges(status)',
            'CREATE INDEX IF NOT EXISTS idx_edges_conflict ON graph_edges(context_flags) WHERE context_flags LIKE "%has_conflict%"',
            'CREATE INDEX IF NOT EXISTS idx_episodic_last_accessed ON episodic_log(last_accessed)',
            'CREATE INDEX IF NOT EXISTS idx_episodic_unconsolidated ON episodic_log(consolidated_to_id) WHERE consolidated_to_id IS NULL',
        ]
        for sql in indexes:
            try:
                cur.execute(sql)
            except sqlite3.OperationalError:
                pass

        # FTS5 полнотекстовый индекс по эпизодам
        fts_statements = [
            '''CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
                user_text, echo_response,
                content='episodic_log', content_rowid='id',
                tokenize='unicode61'
            )''',
            '''CREATE TRIGGER IF NOT EXISTS episodic_fts_ai AFTER INSERT ON episodic_log BEGIN
                INSERT INTO episodic_fts(rowid, user_text, echo_response)
                VALUES (new.id, new.user_text, new.echo_response);
            END''',
            '''CREATE TRIGGER IF NOT EXISTS episodic_fts_ad AFTER DELETE ON episodic_log BEGIN
                INSERT INTO episodic_fts(episodic_fts, rowid, user_text, echo_response)
                VALUES ('delete', old.id, old.user_text, old.echo_response);
            END''',
            '''CREATE TRIGGER IF NOT EXISTS episodic_fts_au AFTER UPDATE ON episodic_log BEGIN
                INSERT INTO episodic_fts(episodic_fts, rowid, user_text, echo_response)
                VALUES ('delete', old.id, old.user_text, old.echo_response);
                INSERT INTO episodic_fts(rowid, user_text, echo_response)
                VALUES (new.id, new.user_text, new.echo_response);
            END''',
        ]
        self._fts5_available = True
        for sql in fts_statements:
            try:
                cur.execute(sql)
            except sqlite3.OperationalError:
                self._fts5_available = False
                break
        if self._fts5_available:
            self.logger.info("FTS5 индекс episodic_fts создан.")
        else:
            self.logger.warning("FTS5 недоступен — EpisodicMemory использует LIKE-поиск.")

        self.conn.commit()
        self.logger.info("База данных инициализирована")

    def execute(self, query, params=()):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(query, params)
            self.conn.commit()
            return cur

    def fetchone(self, query, params=()):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(query, params)
            return cur.fetchone()

    def fetchall(self, query, params=()):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()

    def executemany(self, query, params_seq):
        """Пакетная запись (используется EpisodicMemory для сброса буфера)."""
        with self.lock:
            cur = self.conn.cursor()
            cur.executemany(query, params_seq)
            self.conn.commit()
            return cur

    def fts5_available(self) -> bool:
        """Доступен ли FTS5 полнотекстовый поиск для эпизодов."""
        return getattr(self, "_fts5_available", False)