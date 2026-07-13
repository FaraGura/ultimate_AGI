from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# Основные файлы и папки
DATABASE_FILE = "unified_memory_v14.db"
ASSISTANT_CONFIG_FILE = "assistant_config_v14.json"
KNOWLEDGE_INPUT_DIR = "knowledge_input"
LOGS_DIR = "logs"
DATA_DIR = "data"

# Файлы логов
LOG_FILE = f"{LOGS_DIR}/echo_log.txt"
SKILL_LOG_FILE = f"{LOGS_DIR}/echo_skill.log"
TRAINING_RUN_LOG_FILE = f"{LOGS_DIR}/training.log"
BUILD_RUN_LOG_FILE = f"{LOGS_DIR}/build.log"

# Данные и модели
TRAINING_DATA_FILE = f"{DATA_DIR}/processed/train_data.jsonl"
TEACHER_DATA_FILE = f"{DATA_DIR}/teacher/teacher_lessons.jsonl"
MODEL_INFO_FILE = "models/model_info.json"
LORA_OUTPUT_DIR = "models/echo-lora"
MERGED_MODEL_DIR = "models/echo-merged"
GGUF_MODEL_PATH = "models/qwen-1_5b.gguf"
LLAMA_CPP_DIR = "llama.cpp"

# Seed-файлы для ядра
LANGUAGE_KERNEL_PATH = f"{DATA_DIR}/language_kernel.json"
CORE_AXIOMS_PATH = f"{DATA_DIR}/core_axioms.json"

SUPPORTED_KNOWLEDGE_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".tsv"}