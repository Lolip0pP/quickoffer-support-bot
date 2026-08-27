# QuickOffer Support Bot - Бенчмарк QA системы

## Обзор

Этот бенчмарк оценивает работоспособность системы ответов на вопросы (QA) поддерживающего бота. Система использует три источника ответов в следующем приоритете:

1. **Instruction Flows** - предопределённые сценарии из `docs/instruction.md`
2. **RAG History** - гибридный поиск в исторических диалогах (BM25 + семантический + реранжирование)
3. **LLM Fallback** - резервный вариант с LLM (не реализован в бенчмарке)

## Результаты последнего запуска

```
Дата: 2026-08-20 20:48:13
Всего вопросов: 10
Успешность: 100% (ответ найден на все вопросы)

Статистика по источникам:
├─ Instruction Flow: 6 вопросов (60.0%)
├─ RAG History: 4 вопроса (40.0%)
├─ LLM Fallback: 0 вопросов (0.0%)
└─ Нет ответа: 0 вопросов (0.0%)

Средняя уверенность: 0.79 (высокий уровень)

Распределение уверенности:
├─ Очень высокая (>= 0.85): 1 вопрос
├─ Высокая (0.7-0.85): 8 вопросов
├─ Средняя (0.5-0.7): 1 вопрос
├─ Низкая (0.3-0.5): 0 вопросов
└─ Очень низкая (< 0.3): 0 вопросов
```

## Архитектура компонентов

### 1. FlowMatcher (`src/benchmarking/flow_matcher.py`)

Матчит вопросы пользователя с предопределёнными флоу из инструкций с поддержкой приоритетной обработки эскалаций.

**Доступные флоу (из instruction.md):**
1. `return_refund` - Процесс возврата и заморозки подписки
2. `career_assistance` - Карьерная помощь и консультации экспертов
3. `job_archival` - Архивация вакансий и их удаление из выдачи
4. `referral_promo` - Реферальный промокод и программа рефералов
5. `review_promo` - Промокод за отзыв о сервисе
6. `crypto_payment` - Оплата криптовалютой или иностранной картой
7. `account_deletion` - Удаление аккаунта и данных
8. `search_configuration` - Настройка поиска и фильтров вакансий
9. `subscription_management` - Управление подпиской и автопродлением
10. `response_sending` - Отправка откликов и лимиты
11. `account_access` - Проблемы с входом в аккаунт

**Специальные флоу:**
- `escalation_bug_compensation` - Критические тикеты (баг + компенсация) требующие одобрения сотрудника

**Механизм матчинга:**
- Поиск ключевых слов в вопросе (0.15 балла за совпадение)
- Проверка регулярных выражений (0.25 балла за совпадение)
- Финальный скор нормализуется до [0, 1]
- Минимальный порог совпадения: 0.3

**Пример использования:**
```python
from src.benchmarking.flow_matcher import FlowMatcher

matcher = FlowMatcher()
result = matcher.match("Хочу вернуть деньги за подписку")

if result:
    print(f"Matched: {result.flow_name}")
    print(f"Score: {result.match_score}")
    print(f"Keywords: {result.matched_keywords}")
```

### 2. RAGRetriever (`src/benchmarking/rag_retriever.py`)

**ОБНОВЛЕНО**: Теперь использует гибридный поиск (BM25 + семантический + реранжирование) вместо простого BM25.

Ищет релевантные Q&A пары в историческом датасете используя комбинированный подход для лучшей релевантности.

**Параметры:**
- Алгоритм: Гибридный поиск (30% BM25 + 70% семантический + реранжирование)
- Источник данных: `docs/rag_dataset.jsonl` (5793 Q&A пары)
- Вывод: top-k результатов (по умолчанию 1)
- Embedding модель: `Nestle/qwen-embed-06`
- Reranker модель: `Nestle/qwen-rerank-06`

**Пример использования:**
```python
from src.benchmarking.rag_retriever import RAGRetriever

retriever = RAGRetriever("docs/rag_dataset.jsonl")
matches = retriever.retrieve("Как настроить поиск?", top_k=3)

for match in matches:
    print(f"Q: {match.question}")
    print(f"A: {match.answer}")
    print(f"Score: {match.relevance_score}")  # Используется rerank score
    print()
```

**Примечание:** RAGRetriever теперь является обёрткой над HybridRetriever для обратной совместимости с простым интерфейсом, при этом используя все преимущества гибридного поиска.

### 2.1. HybridRetriever (`src/benchmarking/hybrid_retriever.py`)

**НОВОЕ**: Гибридный поиск с использованием BM25, семантических эмбеддингов и реранжирования.

Комбинирует несколько методов поиска для достижения лучшей релевантности результатов:
1. **BM25 фильтр** - быстрое первичное отсеивание документов
2. **Семантический поиск** - получение эмбеддингов через `Nestle/qwen-embed-06` и вычисление косинусного сходства
3. **Гибридное комбинирование** - взвешенное объединение (30% BM25 + 70% семантический)
4. **Реранжирование** - финальное переранжирование через `Nestle/qwen-rerank-06`

**Параметры:**
- BM25 вес: 0.3 (быстрый лексический поиск)
- Семантический вес: 0.7 (смысловое сходство)
- Embedding модель: `Nestle/qwen-embed-06`
- Reranker модель: `Nestle/qwen-rerank-06`
- Источник данных: `docs/rag_dataset.jsonl` (5793 Q&A пары)

**Особенности:**
- Кэширование эмбеддингов документов (вычисляются один раз при загрузке)
- Кэширование эмбеддингов запросов
- Fallback на комбинированные scores если reranker недоступен
- Подробное логирование всех этапов поиска

**Пример использования:**
```python
from src.benchmarking.hybrid_retriever import HybridRetriever

retriever = HybridRetriever(
    dataset_path="docs/rag_dataset.jsonl",
    base_url="https://litellm.ai.nestle.ru/v1",
    api_key="your-api-key",
    use_reranker=True
)

matches = retriever.retrieve("Как настроить поиск?", top_k=3)

for match in matches:
    print(f"Q: {match.question}")
    print(f"BM25 Score: {match.bm25_score}")
    print(f"Semantic Score: {match.semantic_score}")
    print(f"Combined Score: {match.combined_score}")
    print(f"Rerank Score: {match.rerank_score}")
    print(f"A: {match.answer}\n")
```

**Результаты поиска (HybridRAGMatch):**
- `bm25_score`: Оценка BM25 (0-10+)
- `semantic_score`: Косинусное сходство эмбеддингов (0-1)
- `combined_score`: Взвешенное объединение (0-1)
- `rerank_score`: Оценка реранкера (используется в confidence calculator)

### 3. ConfidenceCalculator (`src/benchmarking/confidence_calculator.py`)

Расчитывает уверенность в ответе в зависимости от источника.

**Базовые значения уверенности:**
- Instruction Flow: 0.9 (базовое)
- RAG History: 0.7 (базовое)
- LLM Fallback: 0.5 (базовое)
- No Match: 0.0

**Модификаторы:**
- Flow Match Score: прямой коэффициент (0.8 + score * 0.2)
- RAG Relevance: нормализуется от BM25 скора (старый метод) или от rerank скора (новый)
- RAG Answer Length: бонус за полноту ответа
- LLM Uncertainty: штраф за фразы неуверенности

**Методы расчета:**
1. `calculate_flow_confidence()` - для Instruction Flow (базовое 0.9)
2. `calculate_rag_confidence()` - для BM25 RAG (базовое 0.7, устарел)
3. `calculate_hybrid_rag_confidence()` - для гибридного RAG с реранжированием (**НОВОЕ**)
4. `calculate_llm_confidence()` - для LLM fallback (базовое 0.5)

**Уровни уверенности:**
- Very High: >= 0.85
- High: 0.7-0.85
- Medium: 0.5-0.7
- Low: 0.3-0.5
- Very Low: < 0.3

**Пример использования:**
```python
from src.benchmarking.confidence_calculator import ConfidenceCalculator

# Для Flow Match
conf = ConfidenceCalculator.calculate_flow_confidence(flow_match_score=0.65)
print(f"Confidence: {conf}")  # 0.83

# Для RAG Match (BM25 - старый метод)
conf = ConfidenceCalculator.calculate_rag_confidence(
    relevance_score=12.44,
    answer_length=150
)
print(f"Confidence: {conf}")  # 0.71

# Для гибридного RAG с реранжированием (НОВОЕ)
conf = ConfidenceCalculator.calculate_hybrid_rag_confidence(
    rerank_score=0.85,
    answer_length=150
)
print(f"Confidence: {conf}")  # 0.81

# Получить уровень
level = ConfidenceCalculator.get_confidence_level(0.79)
print(f"Level: {level}")  # "high"
```

### 4. ApprovalTokenGenerator (`src/benchmarking/approval_generator.py`)

Генерирует токены одобрения для выполнения действий при матчинге флоу.

**Структура токена:**
```
{token_id}_{hash[:16]}
```

**Компоненты токена:**
- `token_id`: UUID4 идентификатор
- `action_id`: ID флоу (e.g., "subscription_management")
- `staff_id`: ID пользователя системы
- `payload_hash`: SHA256 хэш параметров
- `timestamp`: время создания
- `expiry`: время истечения (30 минут)

**Пример использования:**
```python
from src.benchmarking.approval_generator import ApprovalTokenGenerator

gen = ApprovalTokenGenerator()
token = gen.generate_benchmark_token("return_refund")
print(f"Token: {token}")

# Проверка
is_valid = gen.verify_token(token, "return_refund", {})
print(f"Valid: {is_valid}")
```

### 5. Benchmark (`src/benchmarking/benchmark.py`)

Основной скрипт, который оркестрирует работу всех компонентов.

**Процесс:**
1. Инициализация компонентов
2. Извлечение 10 тестовых вопросов из `docs/rag_dataset.jsonl`
3. Обработка каждого вопроса через конвейер:
   - Матчинг с флоу
   - RAG поиск (если флоу не найден)
   - LLM fallback (если RAG не найден)
4. Расчет уверенности для каждого результата
5. Генерация approval token для matched флоу
6. Сохранение результатов в JSON

### 6. InteractiveDemo (`src/benchmarking/interactive_demo.py`)

Интерактивное CLI приложение для тестирования системы в режиме реального времени.

**Особенности:**
- Интерактивный ввод вопросов пользователем
- Использование гибридного RAG retriever (BM25 + семантический + реранжирование)
- Полный конвейер обработки: Flow Matching → Hybrid RAG → LLM Improvement/Fallback
- Отображение всех этапов обработки и деталей поиска
- Поддержка команд выхода: `exit`, `quit`, `q`

**Процесс обработки вопроса:**
1. **STAGE 1**: Flow Matching - поиск в предопределённых сценариях
2. **STAGE 2**: Hybrid RAG Retrieval - гибридный поиск в историческом датасете
   - Отображает BM25, семантический, комбинированный и rerank scores
3. **STAGE 3**: LLM Improvement/Fallback - улучшение ответа или генерация fallback

**Пример использования:**
```bash
python -m src.benchmarking.interactive_demo
```

**Вывод для найденного RAG ответа:**
```
[STAGE 2] Searching in RAG dataset (Hybrid Search)...
  [YES] Found relevant Q&A (rerank score: 0.85)
    BM25: 4.25, Semantic: 0.92
  Similar question: Как настроить фильтры поиска?...
  Answer: Для настройки фильтров выполните следующие шаги...

RESULT
Confidence: 0.81 (high)

Processing Pipeline:
  [1] FLOW_MATCHING: NOT_MATCHED
  [2] RAG_RETRIEVAL: FOUND
      Scores:
        BM25: 4.25
        Semantic: 0.92
        Combined: 0.87
        Rerank: 0.85
```

## Запуск бенчмарка

### Требования
```bash
pip install rank-bm25>=0.2.2
```

### Быстрый старт
```bash
cd c:\Users\rushulpian\Desktop\quickoffer-support-bot
python -m src.benchmarking.benchmark
```

### Результаты
Результаты сохраняются в `benchmark_results.json`:

```json
{
  "benchmark_id": "ce80108e-f2bb-49af-b100-6a87184df716",
  "timestamp": "2026-08-20T17:48:13.948482",
  "total_questions": 10,
  "results": [
    {
      "question_id": "q_1",
      "question": "вопрос...",
      "flow_matched": "subscription_management",
      "flow_match_score": 0.4,
      "source": "instruction_flow",
      "answer": "...",
      "confidence": 0.79,
      "confidence_level": "high",
      "approval_token": "45734b3c-...",
      "processing_stages": [...]
    },
    ...
  ],
  "summary": {
    "flow_match_rate": "60.0%",
    "average_confidence": 0.79,
    "sources_breakdown": {
      "instruction_flow": "60.0%",
      "rag_history": "40.0%",
      "llm_fallback": "0.0%",
      "no_match": "0.0%"
    },
    "confidence_distribution": {
      "very_high": 1,
      "high": 8,
      "medium": 1,
      "low": 0,
      "very_low": 0
    }
  }
}
```

## Логирование

Бенчмарк выводит подробные логи в консоль и сохраняет их в `benchmark.log`:

```
2026-08-20 20:48:13 | INFO | Benchmark initialization...
2026-08-20 20:48:13 | INFO | RAG dataset loaded: 5793 Q&A pairs indexed
2026-08-20 20:48:13 | INFO | Processing question 1/10...
2026-08-20 20:48:13 | INFO | [STAGE 1] Matching with instruction flows...
2026-08-20 20:48:13 | INFO |   [YES] FLOW MATCHED: subscription_management (score: 0.4)
2026-08-20 20:48:13 | INFO | [RESULT] q_1
2026-08-20 20:48:13 | INFO |   Source: instruction_flow
2026-08-20 20:48:13 | INFO |   Confidence: 0.79 (high)
```

## Интеграция в основную систему

### Использование FlowMatcher в боте
```python
from src.benchmarking.flow_matcher import FlowMatcher

flow_matcher = FlowMatcher()

async def handle_user_message(message: str) -> Optional[str]:
    flow = flow_matcher.match(message)
    
    if flow:
        # Пользователь описал проблему, которая соответствует одному из флоу
        return generate_flow_response(flow)
    else:
        # Флоу не найден, используем RAG
        return search_rag_history(message)
```

### Использование RAGRetriever
```python
from src.benchmarking.rag_retriever import RAGRetriever

retriever = RAGRetriever()

async def search_rag_history(query: str) -> str:
    matches = retriever.retrieve(query, top_k=1)
    if matches:
        return matches[0].answer
    return "Unable to find answer"
```

### Использование ConfidenceCalculator
```python
from src.benchmarking.confidence_calculator import ConfidenceCalculator

async def add_confidence_to_response(answer: dict, source: str) -> dict:
    if source == "instruction_flow":
        confidence = ConfidenceCalculator.calculate_flow_confidence(
            answer["flow_match_score"]
        )
    elif source == "rag_history":
        confidence = ConfidenceCalculator.calculate_rag_confidence(
            answer["relevance_score"],
            len(answer["text"])
        )
    else:
        confidence = 0.3
    
    answer["confidence"] = confidence
    answer["confidence_level"] = ConfidenceCalculator.get_confidence_level(confidence)
    return answer
```

## Метрики производительности

### По типам вопросов

| Тип | Вопросов | Erfolgsrate | Средняя уверенность | Источник |
|-----|----------|-------------|---------------------|----------|
| Управление подпиской | 3 | 100% | 0.80 | Flow/RAG |
| Отправка откликов | 3 | 100% | 0.84 | Flow |
| Настройка поиска | 1 | 100% | 0.82 | Flow |
| Прочие | 3 | 100% | 0.73 | RAG |

### Распределение по источникам

```
Instruction Flow (60%)  ████████████████████
RAG History (40%)       █████████████
LLM Fallback (0%)       
No Match (0%)           
```

### Потребление ресурсов

- Инициализация: ~0.08 сек
- Загрузка RAG датасета: ~0.08 сек (5793 пары)
- Обработка одного вопроса: ~0.05 сек (в среднем)
- Общее время выполнения: ~0.15 сек на 10 вопросов

## Новые возможности (v0.2.0)

### 1. RAG Synthesizer - LLM-генерация над RAG ✓

**Проблема:** RAG возвращает сырые тексты из диалогов, содержащие артефакты ("передала ребятам", "секундочку", обрывы фраз).

**Решение:** `LLMImprover` с расширенным system prompt для синтеза чистых, профессиональных ответов.

**Как работает:**
1. RAG найденный контекст передается в `LLMImprover.improve_answer()`
2. LLM очищает текст от диалог-артефактов
3. Переформатирует в тон инструкций QuickOffer
4. Исправляет обрывы фраз и неполные предложения

**Пример:**
```
RAG ответ:    "передала ребятам, секундочку проверим... можешь вернуть деньги"
Улучшенный:   "Для возврата денег выполните следующие шаги:
               1. Перейдите в раздел 'Платежи'
               2. Нажмите 'Запросить возврат'
               3. Выберите платеж и причину"
```

**Включение:** Автоматически включается для RAG ответов с confidence < 0.65. Может быть активирован всегда через параметр `always_improve=True`.

### 2. Приоритет детерминированных триггеров над RAG ✓

**Проблема:** Запросы с четкими интентами (например, "получить реферальный промокод") могут не матчиться с flow из-за низких порогов.

**Решение:** Расширены паттерны для high-specificity flows:

**Пример для Флоу 4 (referral_promo):**
```
Ключевые слова: реферальный, промокод, referal, promo, код, друзья, заработать, скидка
Паттерны:
  - (реферальн|referal).*код
  - промокод.*15%
  - друг.*скидка
  - заработать.*друг
```

**Матчинг:**
- Keyword match: +0.15 балла за совпадение
- Pattern match: +0.25 балла за совпадение
- Нормализация: мин(score, 1.0)
- Порог активации: >= 0.5

### 3. Обработка эскалаций и критических тикетов ✓

**Проблема:** Запросы типа "баг + компенсация/деньги" требуют одобрения сотрудника, но система выдает автоматический ответ.

**Решение:** Новый flow `escalation_bug_compensation` с флагом `needs_staff_approval`.

**Механизм детектирования:**
```
Ключевые слова (баг/ошибка):
  баг, ошибка, bug, error, не работает, сломал, crash, проблема

Ключевые слова (компенсация/деньги):
  компенсация, возмещение, деньги, refund, compensation, money, возврат, выплата

Эскалация срабатывает если ОБА набора слов присутствуют в вопросе.
```

**Обработка при срабатывании:**
- Матчинг: Высочайший приоритет (проверяется ДО остальных flows)
- Source: `escalation_requires_approval`
- Ответ: "This case requires staff review and approval. Our team will contact you shortly."
- Confidence: 0.3 (низкий, чтобы отметить неопределенность)
- Флаг: `needs_staff_approval = True`
- Тип: `escalation_type = "bug_with_compensation"`

**Пример вопроса:**
```
"У меня ошибка в приложении, я не могу отправлять отклики уже 2 дня.
 Требую компенсацию за потерянное время!"

→ ESCALATION DETECTED: bug_with_compensation
→ Flagged for staff approval
→ Не отправляется автоматический ответ
```

## Рекомендации по улучшению

1. **Расширить флоу**: Добавить новые типы вопросов на основе анализа логов
2. **Улучшить матчинг**: Использовать семантические эмбеддинги вместо BM25
3. **Интегрировать LLM**: Подключить OpenAI API для fallback случаев
4. **Добавить feedback loop**: Собирать feedback от пользователей для улучшения
5. **Мониторинг**: Отслеживать метрики confidence в production
6. **Fine-tuning эскалаций**: Настроить набор ключевых слов на основе реальных данных

## Troubleshooting

### Ошибка: "RAG dataset not found"
```
Решение: Убедитесь, что docs/rag_dataset.jsonl существует в проекте
```

### Ошибка: "No Q&A pairs found in dataset"
```
Решение: Проверьте формат JSONL файла - каждая строка должна быть валидным JSON
```

### Низкая уверенность в ответах
```
Решение: 
1. Увеличьте пороги матчинга в FlowMatcher
2. Улучшите качество RAG датасета
3. Добавьте больше флоу для распространенных вопросов
```

## Файлы компонентов

```
src/benchmarking/
├── __init__.py
├── benchmark.py              # Основной скрипт с автоматическим бенчмарком
├── interactive_demo.py       # Интерактивное CLI приложение (НОВОЕ)
├── flow_matcher.py           # Матчинг с флоу
├── rag_retriever.py          # Гибридный RAG поиск (обёртка над HybridRetriever)
├── hybrid_retriever.py       # Гибридный поиск: BM25 + семантический + реранжирование
├── confidence_calculator.py  # Расчет уверенности
├── approval_generator.py     # Генерация токенов одобрения
├── llm_flow_matcher.py       # LLM-based flow matching
├── llm_improver.py           # LLM-синтез и улучшение ответов
├── faiss_cache.py            # FAISS индексирование и кэширование
└── approval_generator.py     # Генерация токенов

docs/
├── instruction.md            # Инструкции по флоу
├── rag_dataset.jsonl         # Исторические диалоги (полный датасет)
├── rag_dataset_train.jsonl   # Тренировочная часть датасета
├── rag_dataset_test.jsonl    # Тестовая часть датасета
└── faiss_indexes/            # FAISS индексы для быстрого поиска

Результаты:
├── benchmark_results.json    # JSON с результатами
└── benchmark.log             # Логи выполнения
```

## Контрибьютинг

При добавлении новых флоу:
1. Добавьте в `FlowMatcher.FLOWS` с ключевыми словами и регулярными выражениями
2. Обновите документацию с новым типом вопроса
3. Запустите бенчмарк и проверьте метрики
4. Добавьте тестовые вопросы для нового флоу в `docs/rag_dataset.jsonl`

---

**Версия**: 0.2.0  
**Дата обновления**: 2026-08-20  
**Автор**: QuickOffer Support Bot Team

## Changelog

### v0.3.0 (2026-08-22)
- ✓ **RAGRetriever как обёртка**: RAGRetriever теперь использует HybridRetriever под капотом для полной совместимости
- ✓ **InteractiveDemo обновления**: Добавлено интерактивное CLI приложение с полным гибридным поиском
  - Отображение всех компонентов оценки: BM25, семантический, комбинированный и rerank scores
  - Использование calculate_hybrid_rag_confidence для корректного расчета уверенности
  - Поддержка LLM улучшения ответов и fallback генерации
- ✓ **Документация**: Обновлена BENCHMARK_README с описанием InteractiveDemo и обновлённого RAGRetriever

### v0.2.0 (2026-08-20)
- ✓ **RAG Synthesizer**: Добавлена LLM-генерация над RAG с очисткой диалог-артефактов
- ✓ **Расширенные flows**: Добавлены все 6 flows из instruction.md (career_assistance, job_archival, referral_promo, review_promo, crypto_payment)
- ✓ **Приоритет детерминированных триггеров**: Расширены паттерны для high-specificity flows
- ✓ **Обработка эскалаций**: Добавлен flow escalation_bug_compensation для критических тикетов (баг + компенсация)
- ✓ **Метаданные эскалации**: Добавлены флаги needs_staff_approval и escalation_type в BenchmarkResult

### v0.1.0 (2026-08-15)
- Базовая реализация FlowMatcher с 6 flows
- HybridRetriever с BM25 + семантическим поиском + реранжированием
- ConfidenceCalculator для расчета уверенности ответов
- ApprovalTokenGenerator для генерации токенов одобрения
