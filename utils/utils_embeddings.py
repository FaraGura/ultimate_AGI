# util/utils_embeddings.py

import os
from typing import Optional
from utils.utils_logger import get_logger


class EmbeddingProvider:
    def __init__(self, logger=None):
        self.logger = logger or get_logger("EmbeddingProvider")
        self.model = None
        self._init_local_model()

    def _init_local_model(self):
        """Загружает локальную модель rubert-tiny2 без интернета."""
        # Блокируем любые попытки выйти в сеть
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "echo_core", "models", "rubert-tiny2"
        )

        # Ищем папку модели (она может быть во вложенной подпапке snapshots/...)
        if not os.path.exists(model_path):
            self.logger.warning(f"Папка модели не найдена: {model_path}")
            return

        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_path, trust_remote_code=False)
            self.logger.info("Локальный эмбеддер rubert-tiny2 загружен (офлайн).")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки локальной модели: {e}")
            self.model = None

    def similarity(self, text1: str, text2: str) -> float:
        """Косинусная схожесть двух текстов. Если модель не загружена, возвращает 0."""
        if self.model is None:
            return 0.0
        try:
            emb1 = self.model.encode([text1], show_progress_bar=False)[0]
            emb2 = self.model.encode([text2], show_progress_bar=False)[0]
            return float(
                (emb1 @ emb2) / (max(1e-9, __import__("numpy").linalg.norm(emb1) * __import__("numpy").linalg.norm(emb2)))
            )
        except Exception:
            return 0.0

    def encode(self, text: str):
        """Возвращает вектор для одного текста. Если модель не загружена, возвращает None."""
        if self.model is None:
            return None
        try:
            return self.model.encode([text], show_progress_bar=False)[0]
        except Exception:
            return None