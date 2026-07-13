import numpy as np
from collections import OrderedDict
from echo_core.config import LOGS_DIR

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

class EmbeddingProvider:
    def __init__(self, logger):
        self.logger = logger
        self.model = None
        self.cache = OrderedDict()
        self.max_cache_size = 200
        if SentenceTransformer is None:
            self.logger.warning("SentenceTransformer не установлен. Эмбеддинги отключены.")
            return
        try:
            self.logger.info("Загружаю Nomic Embed Text v1.5...")
            self.model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')
            self.logger.info("Nomic Embed загружен.")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки Nomic Embed: {e}")
            self.model = None

    def get_embedding(self, text: str) -> np.ndarray:
        if self.model is None:
            return None
        cleaned = text.strip().lower()
        if cleaned in self.cache:
            self.cache.move_to_end(cleaned)
            return self.cache[cleaned]
        emb = self.model.encode(cleaned)
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)
        self.cache[cleaned] = emb
        return emb

    def similarity(self, text1: str, text2: str) -> float:
        if self.model is None:
            return 0.0
        a = self.get_embedding(text1)
        b = self.get_embedding(text2)
        if a is None or b is None:
            return 0.0
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))