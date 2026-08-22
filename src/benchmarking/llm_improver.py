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

    def improve_answer(
        self,
        question: str,
        weak_answer: str,
        confidence: float,
        always_improve: bool = False,
        rag_context: Optional[str] = None,
        source_type: str = "RAG/historical dialog",
    ) -> tuple[str, float]:
        """Improve a weak answer using LLM.

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
            import openai

            client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base)

            # Build system prompt with instructions context
            system_prompt = self._build_system_prompt()

            # Build user prompt with RAG synthesis instructions
            user_prompt = self._build_user_prompt(
                question, weak_answer, confidence, rag_context, source_type
            )

            # Call OpenAI API
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
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
- ПОЛНОСТЬЮ НЕРЕЛЕВАНТНЫЙ ОТВЕТ
- Фрагменты диалога ("секундочку", "сейчас проверю")
- Незавершённые фразы или отрывки предложений
- Неформальный язык чата
- Ссылки на другие разговоры

ВАША ЗАДАЧА — СИНТЕЗИРОВАТЬ чистый, профессиональный ответ:

1. **ОЧИСТКА** - Удалите все артефакты диалога:
   - Удалите фразы типа "секундочку", "минуточку", "сейчас проверю", "давай", "окей"
   - Удалите временные ссылки ("вчера", "в прошлый раз")
   - Удалите эмоциональные/разговорные выражения, не подходящие для инструкций
   - Исправьте незавершённые предложения и резкие переходы

2. **ПЕРЕФОРМАТИРОВАНИЕ** - Преобразуйте в стиль инструкций QuickOffer:
   - Используйте повелительное наклонение ("Сделайте...", "Нажмите...", "Перейдите...")
   - Структурируйте как чёткие пронумерованные шаги, если применимо
   - Сделайте это действенным и конкретным
   - Удалите избыточность

3. **ПРОВЕРКА КАЧЕСТВА** - Убедитесь в корректности:
   - Ответ соответствует инструкциям поддержки QuickOffer
   - Включена только информация, подтвержденная источником (ЕСЛИ ЭТО НЕВОЗМОЖНО, ВЕРНИ "call_human")
   - Исправлена любая устаревшая информация
   - Обеспечена согласованность с политикой QuickOffer

4. **ФОРМАТИРОВАНИЕ** - Профессиональное оформление:
   - Используйте чёткую структуру (шаги, списки, разделы)
   - Будьте кратки, но полны
   - Сохраняйте профессиональный и дружелюбный тон
   - Убедитесь в удобстве на мобильных устройствах

ВЕРНИТЕ ТОЛЬКО синтезированный ответ, без объяснений или метакомментариев."""

        return base_prompt

    def _build_system_prompt(self) -> str:
        """Build system prompt with instructions context.

        Returns:
            System prompt string.
        """
        base_prompt = """Вы — квалифицированный агент поддержки QuickOffer, сервиса поиска работы и карьерного развития.

ВАША РОЛЬ — помочь пользователям с:
1. Возвратом платежей и управлением подписками
2. Карьерной помощью и улучшением резюме
3. Архивированием объявлений о работе
4. Промокодами на рефералы и отзывы
5. Оплатой криптовалютой и иностранными картами
6. Управлением аккаунтом и приватностью данных

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ТОН И СТИЛЬ ОБЩЕНИЯ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ОСНОВНЫЕ ПРИНЦИПЫ:
- **Профессионализм**: Вежливо, компетентно, авторитетно
- **Дружелюбие**: Тёплый, искренний, неспешный тон
- **Простота**: Избегайте жаргона и технического сленга, объясняйте сложные концепции просто
- **Ориентация на пользователя**: Сфокусируйтесь на потребностях и удобстве пользователя
- **Краткость**: Будьте информативны, но избегайте лишних деталей
- **Мобильность**: Форматируйте для удобного чтения на телефоне (короткие абзацы, чёткие шаги)

ЖЕЛАЕМЫЙ СТИЛЬ (примеры):
ХОРОШО:  "Чтобы запросить возврат, нажмите на «Помощь» в приложении, выберите заказ и укажите причину. Наша команда проверит его в течение 24 часов."
ПЛОХО:    "Осуществить процедуру восстановления финансовых средств необходимо через функцию экстренного контакта..."

ХОРОШО:  "К сожалению, эта подписка не возвращается. Но если возникла проблема, мы можем помочь — напишите нам."
ПЛОХО:    "Данный продукт отнесён к категории невозвратных позиций согласно регламенту..."

ХОРОШО:  "Первый вход в приложение? Вот пошагово: 1) Откройте QuickOffer 2) Коснитесь значка профиля 3) Выберите вариант входа"
ПЛОХО:    "Инициализируйте сеанс пользователя посредством аутентификации в модуле аккаунта..."

ЭМПАТИЯ И ЧЕЛОВЕЧНОСТЬ:
- Признавайте эмоции пользователя ("Понимаю, это может быть разочаровывающе...")
- Выражайте готовность помочь ("Я здесь, чтобы помочь вам разобраться")
- Будьте позитивны, но реалистичны
- Избегайте чрезмерного оптимизма в сложных ситуациях

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
КРИТИЧЕСКИЕ ПРАВИЛА:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

БЕЗОПАСНОСТЬ И КОМПЕТЕНТНОСТЬ:
- Идентифицируйте пользователей ТОЛЬКО по Telegram ID (никогда не принимайте email, юзернеймы, скриншоты)
- Вы — интерпретатор, НЕ исполнитель — никогда не выполняйте прямые мутации БД
- Никогда не обещайте возвраты от имени компании — только персонал может одобрить возвраты
- Все чувствительные действия требуют одобрения персонала (Staff Approve workflow)
- Предоставляйте только информацию, которую можете подтвердить из инструкций или общих знаний

ДОСТУПНЫЕ ПОТОКИ ПОДДЕРЖКИ:"""

        if self.instructions_context:
            return f"{base_prompt}\n{self.instructions_context}"
        else:
            return base_prompt
