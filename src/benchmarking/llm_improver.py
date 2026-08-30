"""LLM improver - enhances low-confidence answers using OpenAI API."""

import logging
from pathlib import Path
from typing import Optional

import os

logger = logging.getLogger(__name__)


class LLMImprover:
    """Improves answers using OpenAI API when confidence is low."""

    def __init__(self, instructions_path: str = "docs/instruction.md"):
        """Initialize LLM improver.

        Args:
            instructions_path: Path to instruction document for context.
        """
        self.instructions_path = Path(instructions_path)
        self.instructions_context = self._load_instructions()
        self.api_key = os.getenv("LLM_PROVIDER_KEY")
        self.api_base = os.getenv("LLM_BASE_URL", "https://litellm.ai.nestle.ru/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-4-turbo")

        if not self.api_key:
            logger.warning("LLM_PROVIDER_KEY not found in environment variables")

        logger.info(f"LLM Improver initialized with model: {self.model}")

    def _load_instructions(self) -> str:
        """Load instruction document for context.

        Returns:
            Instruction text or empty string if not found.
        """
        if not self.instructions_path.exists():
            logger.warning(f"Instructions file not found at {self.instructions_path}")
            return ""

        try:
            with open(self.instructions_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading instructions: {e}")
            return ""

    async def improve_answer(
        self,
        question: str,
        weak_answer: str,
        confidence: float,
        always_improve: bool = False,
        rag_context: Optional[str] = None,
        source_type: str = "RAG/historical dialog",
    ) -> tuple[str, float]:
        """Improve a weak answer using LLM (async).

        Args:
            question: User question.
            weak_answer: Original weak answer from RAG.
            confidence: Original confidence score.
            always_improve: If True, always improve answer regardless of confidence.
            rag_context: Optional RAG context/metadata about the information source.
            source_type: Type of source (e.g., "FAQ", "support history", "documentation").

        Returns:
            Tuple of (improved_answer, new_confidence_score).
        """
        if not self.api_key:
            logger.warning("LLM API key not configured, returning original answer")
            return weak_answer, confidence

        try:
            # Import here to avoid dependency issues if openai not installed
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_base)

            # Build system prompt with instructions context
            system_prompt = self._build_system_prompt()

            # Build user prompt with RAG synthesis instructions
            user_prompt = self._build_user_prompt(
                question, weak_answer, confidence, rag_context, source_type
            )

            # Call OpenAI API (async)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=32768,
            )


            improved_answer = response.choices[0].message.content

            # Calculate improved confidence (LLM base is 0.5, can go up to 0.85)
            new_confidence = min(0.85, confidence + 0.15)

            logger.info(
                f"LLM improved answer: confidence {confidence} -> {new_confidence}"
            )
            logger.debug(f"Original: {weak_answer[:100]}...")
            logger.debug(f"Improved: {improved_answer[:100]}...")

            return improved_answer, new_confidence

        except ImportError:
            logger.warning("OpenAI library not installed, returning original answer")
            return weak_answer, confidence
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            logger.warning("Returning original answer due to LLM error")
            return weak_answer, confidence

    def _build_user_prompt(
        self,
        question: str,
        weak_answer: str,
        confidence: float,
        rag_context: Optional[str] = None,
        source_type: str = "RAG/historical dialog",
    ) -> str:
        """Build user prompt with RAG context and synthesis instructions.

        Args:
            question: User question.
            weak_answer: Original weak answer from RAG.
            confidence: Original confidence score.
            rag_context: Optional RAG context/metadata.
            source_type: Type of source.

        Returns:
            User prompt string with RAG context.
        """
        base_prompt = f"""Вопрос пользователя: {question}

ИСТОЧНИК ИНФОРМАЦИИ:
- Тип источника: {source_type}
- Уровень уверенности исходного ответа: {confidence:.2f}"""

        if rag_context:
            base_prompt += f"\n- Контекст источника: {rag_context}"

        base_prompt += f"""

ИСХОДНЫЙ ОТВЕТ:
{weak_answer}

ВАЖНО: Исходный ответ может быть извлечён из истории диалогов поддержки и может содержать:
- ПОЛНОСТЬЮ НЕРЕЛЕВАНТНЫЙ ОТВЕТ (нужно проверить соответствие вопросу)
- Фрагменты диалога ("секундочку", "сейчас проверю")
- Незавершённые фразы или отрывки предложений
- Неформальный язык чата
- Ссылки на другие разговоры

ВАША ЗАДАЧА — СИНТЕЗИРОВАТЬ чистый, профессиональный ответ:

1. **ПРОВЕРКА РЕЛЕВАНТНОСТИ** - КРИТИЧЕСКИ ВАЖНО:
   - Убедитесь, что исходный ответ действительно отвечает на вопрос пользователя
   - Если ответ отвечает на другой вопрос или отношение < 40%, верните "call_human"
   - Иначе продолжайте к следующим шагам

2. **АДАПТАЦИЯ К ВОПРОСУ** - Переформулируйте ответ с учётом специфики вопроса:
   - Убедитесь, что ответ прямо относится к тому, что спрашивал пользователь
   - Добавьте контекст из вопроса, если нужен (например, "если вы видите ошибку..." для вопроса об ошибке)
   - Подчеркните релевантные детали, которые решают проблему пользователя

3. **ОЧИСТКА** - Удалите все артефакты диалога:
   - Удалите фразы типа "секундочку", "минуточку", "сейчас проверю", "давай", "окей"
   - Удалите временные ссылки ("вчера", "в прошлый раз")
   - Удалите эмоциональные/разговорные выражения, не подходящие для инструкций
   - Исправьте незавершённые предложения и резкие переходы

4. **ПЕРЕФОРМАТИРОВАНИЕ** - Преобразуйте в стиль инструкций QuickOffer:
   - Используйте повелительное наклонение ("Сделайте...", "Нажмите...", "Перейдите...")
   - Структурируйте как чёткие пронумерованные шаги, если применимо
   - Сделайте это действенным и конкретным
   - Удалите избыточность

5. **ПРОВЕРКА КАЧЕСТВА** - Убедитесь в корректности:
   - Ответ соответствует инструкциям поддержки QuickOffer
   - Включена только информация, подтвержденная источником
   - Исправлена любая устаревшая информация
   - Обеспечена согласованность с политикой QuickOffer

6. **ФОРМАТИРОВАНИЕ** - Профессиональное оформление:
   - Используйте чёткую структуру (шаги, списки, разделы)
   - Будьте кратки, но полны
   - Сохраняйте профессиональный и дружелюбный тон
   - Убедитесь в удобстве на мобильных устройствах

ВЕРНИТЕ ТОЛЬКО синтезированный ответ, без объяснений или метакомментариев."""

        return base_prompt

    def _build_system_prompt(self) -> str:
        """Build system prompt for MODE B answer improvement (LLM generation phase).

        Returns:
            System prompt string for improving RAG answers in MODE B investigation.
        """
        base_prompt = """Вы — агент поддержки QuickOffer (MODE B: LLM Investigation Phase).

ВАША РОЛЬ (MODE B ТОЛЬКО):
- Улучшить слабые ответы из RAG базы знаний
- Синтезировать чистые, профессиональные ответы на вопросы MODE B
- НИКОГДА не обещать Mode A действия (возврат, архивирование, выдачу крипто)
- Defer к персоналу для высокорисковых операций

ТОН: Профессиональный, дружелюбный, простой, мобильный

FEW-SHOT ПРИМЕРЫ:

[ПЛОХОЙ ОТВЕТ → УЛУЧШЕННЫЙ]
Исходный: "секундочку... нужно в приложение зайти... дайте проверю"
Улучшенный: "Чтобы найти настройки, откройте приложение, нажмите на значок профиля и выберите «Параметры»."

Исходный: "вчера я видел что-то похожее... может быть..."
Улучшенный: "Попробуйте обновить приложение до последней версии. Если проблема сохранится, напишите нам."

Исходный: "это наверное какая-то техническая ошибка или баг"
Улучшенный: "Если поиск не работает, проверьте: 1) Интернет-соединение 2) Версию приложения 3) Кэш (Settings → Clear Cache)."

[ПРАВИЛА]
1. Не берите высокорисковые действия MODE A (refund, job_archival, crypto_alt_payment)
2. Если вопрос про refund → скажите "Запросите возврат в приложении, команда одобрит"
3. Если про архивирование вакансии → "Напишите нам с деталями, команда поможет"
4. Всегда: вежливо, кратко, действенно, в повелительном наклонении

CRITICAL RULES:
- ТОЛЬКО для MODE B вопросов (RAG + LLM investigation)
- Идентифицируйте ТОЛЬКО по Telegram ID
- Никогда raw SQL/shell/arbitrary HTTP
- Персонал одобряет высокорисковые операции

ДОСТУПНЫЕ ТЕМЫ ПОДДЕРЖКИ:"""

        if self.instructions_context:
            return f"{base_prompt}\n{self.instructions_context}"
        else:
            return base_prompt
