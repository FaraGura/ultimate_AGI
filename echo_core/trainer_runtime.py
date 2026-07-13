# echo_core/trainer_runtime.py
"""
Конвейер дообучения Echo через LM Studio.
Адаптирован из ветки test_eho-main.
Запускается в фазе сна для улучшения модели.
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime
from utils.utils_logger import get_logger


class TrainingPipeline:
    """
    Управляет процессом дообучения модели через LM Studio.
    Интегрирован с фазой сна Echo.
    """
    def __init__(self, db, config=None):
        self.logger = get_logger("TrainingPipeline")
        self.db = db
        self.config = config or {}
        self.training_data_path = "data/processed/train_data.jsonl"
        self.lora_output_dir = "models/echo-lora"
        self.lm_studio_url = "http://localhost:1234/v1/chat/completions"
        
    def prepare_dataset(self) -> int:
        """
        Собирает датасет из всех источников знаний Echo.
        Возвращает количество собранных примеров.
        """
        examples = []
        
        # 1. Факты из CausalGraph
        edges = self.db.fetchall(
            "SELECT source_concept, target_concept, relation_type, confidence FROM causal_edges WHERE confidence > 0.5"
        )
        for source, target, relation, conf in edges:
            examples.append({
                "instruction": f"Что ты знаешь о связи {source} и {target}?",
                "output": f"{source} {relation} {target} (уверенность: {conf:.2f})",
                "source": "causal_graph"
            })
        
        # 2. Законы из survival_matrix
        laws = self.db.fetchall(
            "SELECT context, core_essence, actionable_wisdom, confidence_score FROM survival_matrix WHERE confidence_score > 0.7"
        )
        for context, essence, wisdom, conf in laws:
            examples.append({
                "instruction": f"Расскажи о: {context}",
                "output": f"{essence}. {wisdom}",
                "source": "survival_matrix"
            })
        
        # 3. Знания из learned_knowledge
        knowledge = self.db.fetchall(
            "SELECT content, knowledge_type FROM learned_knowledge WHERE weight > 0.5"
        )
        for content, ktype in knowledge:
            examples.append({
                "instruction": "Расскажи факт",
                "output": content,
                "source": "learned_knowledge"
            })
        
        # 4. Определения из graph_nodes
        nodes = self.db.fetchall(
            "SELECT payload FROM graph_nodes WHERE node_type = 'concept' AND provenance_source = 'user_teaching'"
        )
        for (payload_blob,) in nodes:
            try:
                payload = json.loads(payload_blob) if isinstance(payload_blob, str) else {}
                value = payload.get("value", "")
                definition = payload.get("definition", "")
                if value and definition:
                    examples.append({
                        "instruction": f"Что такое {value}?",
                        "output": f"{value} — это {definition}",
                        "source": "graph_nodes"
                    })
            except Exception:
                pass
        
        # Сохраняем датасет
        os.makedirs(os.path.dirname(self.training_data_path), exist_ok=True)
        with open(self.training_data_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        
        self.logger.info(f"Датасет собран: {len(examples)} примеров")
        return len(examples)
    
    def run_training(self) -> bool:
        """
        Запускает дообучение через LM Studio.
        Возвращает True при успехе.
        """
        if not os.path.exists(self.training_data_path):
            self.logger.warning("Датасет не найден, запускаю подготовку")
            count = self.prepare_dataset()
            if count == 0:
                self.logger.warning("Нет данных для обучения")
                return False
        
        self.logger.info("Запуск дообучения через LM Studio...")
        
        # Здесь будет вызов LM Studio API для дообучения
        # Пока заглушка — логируем и возвращаем успех
        self.logger.info("Дообучение завершено (заглушка)")
        return True
    
    def run_full_cycle(self) -> bool:
        """
        Полный цикл: подготовка датасета + обучение.
        """
        self.logger.info("=" * 50)
        self.logger.info("НАЧАЛО ЦИКЛА ДООБУЧЕНИЯ")
        self.logger.info("=" * 50)
        
        count = self.prepare_dataset()
        if count == 0:
            self.logger.warning("Цикл прерван: нет данных")
            return False
        
        success = self.run_training()
        if success:
            self.logger.info("Цикл дообучения успешно завершён")
        else:
            self.logger.error("Ошибка в цикле дообучения")
        
        return success