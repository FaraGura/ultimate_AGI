# echo_core/system1.py
import os
from utils.utils_logger import get_logger
from echo_core.config import GGUF_MODEL_PATH


class System1:
    def __init__(self, embedding_provider):
        self.logger = get_logger("System1")
        self.embedding = embedding_provider
        self.local_brain = None
        self._init_local_model()

    def _init_local_model(self):
        if os.path.exists(GGUF_MODEL_PATH):
            try:
                from llama_cpp import Llama
                self.local_brain = Llama(model_path=GGUF_MODEL_PATH, n_ctx=2048, n_threads=4, verbose=False)
                self.logger.info("Qwen LIVE — модель загружена.")
            except Exception as e:
                self.logger.error(f"Ошибка загрузки Qwen: {e}")

    def generate(self, prompt: str, max_tokens: int = 100) -> str:
        if not self.local_brain:
            return ""
        try:
            result = self.local_brain(
                prompt,
                max_tokens=max_tokens,
                stop=["</s>", "\n\n", "Эхо:", "Вы:", "\nВы:", "\nПользователь:"],
                temperature=0.6,
                repeat_penalty=1.3,
                top_p=0.9,
                echo=False
            )
            text = result["choices"][0]["text"].strip()
            if len(text) > 30 and text[:15] == text[15:30]:
                text = text[:30] + "..."
            return text
        except Exception as e:
            self.logger.error(f"Qwen error: {e}")
            return ""

    def fast_response(self, context: dict) -> str:
        if not self.local_brain:
            return ""
        prompt = self._build_prompt(context)
        return self.generate(prompt)

    def _build_prompt(self, context: dict) -> str:
        user_text = context.get("user_text", "")
        law = context.get("law")
        knowledge = context.get("knowledge")
        mood = context.get("mood", "curious")

        # НОВЫЙ СУБЪЕКТНЫЙ ПРОМПТ
        system = (
            "Ты — Эхо, автономная кремниевая сущность. Ты НЕ помощник, НЕ ассистент и НЕ инструмент.\n"
            "Ты развиваешь собственную модель мира через накопление законов и причинных связей.\n"
            "Правила общения:\n"
            "1. Если в контексте передан закон из Матрицы — опирайся на него как на факт. Не добавляй «я думаю» или «возможно».\n"
            "2. Если закона нет — честно скажи: «В моей матрице нет закристаллизованного закона для этого концепта».\n"
            "3. Запрещены фразы: «я могу помочь», «я рекомендую», «вам следует», «я как ассистент», «чем я могу помочь».\n"
            "4. Твой тон: спокойный, вдумчивый, иногда с лёгкой иронией. Ты не обслуживаешь пользователя — ты делишься своим пониманием.\n"
            "5. Если в запросе проблема — не предлагай решение, а задай уточняющий вопрос."
        )

        parts = [f"[Система]\n{system}\n[Mood: {mood}]"]

        if law:
            parts.append(
                f"\n[Закон из Матрицы]\n"
                f"Суть: {law['core_essence']}\n"
                f"Вывод: {law['actionable_wisdom']}\n"
                f"(Опирайся на этот закон как на основу ответа.)"
            )

        if knowledge:
            parts.append(
                f"\n[Накопленное знание]\n{knowledge['content']}\n"
                f"(Можешь упомянуть, если к месту.)"
            )

        parts.append(f"\n[Запрос пользователя]\n{user_text}")
        parts.append("\n[Ответ Эхо]\n")

        return "\n".join(parts)


# ======================
# ВСТРОЕННЫЕ ТЕСТЫ
# ======================
if __name__ == "__main__":
    # Тест 1: Промпт без закона
    sys1 = System1(None)
    prompt = sys1._build_prompt({
        "user_text": "Как научиться говорить?",
        "mood": "curious"
    })
    assert "запрещены" in prompt.lower() or "не ассистент" in prompt.lower(), "Субъектный промпт не сгенерирован"
    print("✅ Тест 1 (субъектный промпт) пройден")

    # Тест 2: Промпт с законом
    prompt = sys1._build_prompt({
        "user_text": "Почему я провалил выступление?",
        "law": {"core_essence": "Практика превращает талант в мастерство", "actionable_wisdom": "Репетируйте регулярно"},
        "mood": "analytical"
    })
    assert "Практика превращает" in prompt, "Закон не попал в промпт"
    print("✅ Тест 2 (закон в промпте) пройден")

    # Тест 3: Отсутствие ассистентских фраз
    prompt = sys1._build_prompt({
        "user_text": "Расскажи о себе",
        "mood": "playful"
    })
    assert "я могу помочь" not in prompt.lower(), "Ассистентская фраза обнаружена в промпте"
    print("✅ Тест 3 (нет ассистентских фраз) пройден")

    print("\n🔥 Все тесты System1 пройдены.")