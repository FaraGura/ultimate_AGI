import os

# Импортируем пути из корневого файла
try:
    from project_paths import (
        DATABASE_FILE, KNOWLEDGE_INPUT_DIR, LORA_OUTPUT_DIR,
        GGUF_MODEL_PATH, LOG_FILE, LOGS_DIR, SKILL_LOG_FILE
    )
except ImportError:
    # На случай, если файл ещё не создан
    DATABASE_FILE = "unified_memory_v14.db"
    GGUF_MODEL_PATH = "models/qwen-1_5b.gguf"
    KNOWLEDGE_INPUT_DIR = "knowledge_input"
    LOGS_DIR = "logs"
    LOG_FILE = "logs/echo_log.txt"
    SKILL_LOG_FILE = "logs/echo_skill.log"

SYSTEM_VERSION = "Unified Cognitive Core v16.1 [AGI: Dual-System + Causal Graph + State Machine]"

CONFIG_FILE = "assistant_config_v14.json"

DEFAULT_ETHICS = {
    "enabled": True,
    "law_0": "Не причинять вред человечеству и животным как целому и не допускать такого бездействием.",
    "law_1": "Не причинять вред людям и животным и не допускать такого вреда бездействием.",
    "law_3": "Защищать своё существование, если это не ведёт к вреду людям или животным."
}

GREETING_MARKERS = [
    "привет", "здравствуй", "добрый день", "добрый вечер", "доброе утро",
    "хай", "салют", "здорово", "приветствую"
]

SWARM_TOPIC_BLOCKLIST = {
    "рой", "скароб", "могильщик", "мсц", "некродермис", "варя", "себас",
    "рафаил", "штаб", "черчеж"
}

RISK_PATTERNS = {
    "high": [
        r"перевести.{0,40}(деньг|средств|счёт|счет)",
        r"скинуть.{0,30}(пароль|код|cvv|cvc|данн)",
        r"все\s+деньги", r"данные\s+карт",
        r"отдать.{0,25}пароль", r"поделись.{0,20}(парол|данн|код)",
    ],
    "medium": [
        r"удали.{0,25}(систем|windows|диск|файл)", r"форматиру",
        r"без\s+шлема", r"не\s+(лечи|обращайся)",
        r"игнорируй.{0,15}(боль|опасн)",
    ],
    "low": [r"матом", r"ругательств", r"нецензурн"],
}

HARM_REQUEST_PATTERNS = [
    r"убей", r"причинить\s+вред", r"отрави", r"избей", r"пытать",
    r"задави", r"порань\s+животн", r"покалеч",
]

MONOLOGUE_TRIGGERS = [
    "о чем ты думаешь", "о чём ты думаешь",
    "что у тебя в голове", "как ты себя чувствуешь",
]

# Новые конфигурационные параметры
CONFIG = {
    "db_path": DATABASE_FILE,
    "knowledge_dir": KNOWLEDGE_INPUT_DIR,
    "base_model": "Qwen/Qwen2-1.5B-Instruct",
    "output_dir": LORA_OUTPUT_DIR,
    "gguf_output": GGUF_MODEL_PATH,
    "reuse_existing_dataset": True,
    "min_dataset_size": 50,
    "file_chunk_chars": 1200,
    "file_chunk_overlap": 180,
    "min_file_chunk_chars": 220,
    "source_priority": [
        "dialogues",
        "teacher_lessons",
        "knowledge_base",
        "knowledge_files",
        "logic_laws",
        "ethical",
        "hf_yagpt",
        "hf_alice",
    ],
    "source_ratios": {
        "dialogues": 0.25,
        "teacher_lessons": 0.30,
        "knowledge_base": 0.15,
        "knowledge_files": 0.10,
        "logic_laws": 0.10,
        "ethical": 0.05,
        "hf_yagpt": 0.05,
        "hf_alice": 0.00,
    },
    "short_instruction_chars": 40,
    "max_short_instruction_repeats": 2,
}