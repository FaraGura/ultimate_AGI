"""
Training Pipeline v2.0 — фоновая тренировка на истории диалогов.
Использует пакетное извлечение фактов (extract_all) для повышения плотности обучения.
"""
import time
import json
from datetime import datetime
from typing import Optional

from utils.utils_logger import get_logger


class TrainingPipeline:
    def __init__(self, db):
        self.db = db
        self.logger = get_logger("TrainingPipeline")

    def run_full_cycle(self) -> int:
        """
        Прогоняет полный цикл обучения на накопленных эпизодах.
        Возвращает количество извлечённых фактов.
        """
        self.logger.info("Запуск полного тренировочного цикла...")
        episodes = self._load_unprocessed_episodes()
        if not episodes:
            self.logger.info("Нет новых эпизодов для обучения.")
            return 0

        total_facts = 0
        for episode in episodes:
            facts = self._process_episode(episode)
            if facts:
                total_facts += len(facts)
                self._mark_episode_processed(episode.get("id"))

        self.logger.info(f"Тренировочный цикл завершён. Извлечено фактов: {total_facts}")
        return total_facts

    def _load_unprocessed_episodes(self) -> list:
        """
        Загружает эпизоды, которые ещё не были обработаны тренировочным пайплайном.
        """
        try:
            rows = self.db.fetchall(
                "SELECT id, user_text, response, created FROM episodic_memory "
                "WHERE training_processed = 0 OR training_processed IS NULL "
                "ORDER BY created ASC LIMIT 100"
            )
            episodes = []
            for row in rows:
                episodes.append({
                    "id": row[0],
                    "user_text": row[1],
                    "response": row[2],
                    "created": row[3],
                })
            return episodes
        except Exception as e:
            self.logger.error(f"Ошибка загрузки эпизодов: {e}")
            return []

    def _process_episode(self, episode: dict) -> Optional[list]:
        """
        Обрабатывает один эпизод: пытается извлечь факты из ответа Echo.
        Использует пакетный extract_all, если доступен.
        """
        try:
            from echo_core.knowledge_extractor import KnowledgeExtractor
            from echo_core.causal_graph import CausalGraph

            # Создаём минимальный контекст для экстрактора
            causal = CausalGraph(self.db)
            extractor = KnowledgeExtractor(causal, self.db)

            response_text = episode.get("response", "")
            if not response_text or len(response_text) < 10:
                return None

            # Пакетное извлечение фактов
            if hasattr(extractor, 'extract_all'):
                facts = extractor.extract_all(response_text)
            else:
                fact = extractor.extract(response_text)
                facts = [fact] if fact else []

            return facts if facts else None
        except Exception as e:
            self.logger.error(f"Ошибка обработки эпизода {episode.get('id')}: {e}")
            return None

    def _mark_episode_processed(self, episode_id: int) -> None:
        """Помечает эпизод как обработанный."""
        try:
            self.db.execute(
                "UPDATE episodic_memory SET training_processed = 1 WHERE id = ?",
                (episode_id,)
            )
        except Exception as e:
            self.logger.error(f"Ошибка отметки эпизода: {e}")