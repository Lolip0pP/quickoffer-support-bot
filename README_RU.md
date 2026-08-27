# QuickOffer Support Bot - Полная документация

Русская документация по архитектуре, реализации всех компонентов, и операционной работе поддержки.

## 📋 Оглавление

1. [Обзор](#обзор)
2. [Архитектура двойного режима](#архитектура-двойного-режима)
3. [Режим A: Детерминированные потоки](#режим-a-детерминированные-потоки)
4. [Режим B: LLM расследование и эскалация](#режим-b-llm-расследование-и-эскалация)
5. [Компоненты и сервисы](#компоненты-и-сервисы)
6. [Тестирование и бенчмарки](#тестирование-и-бенчмарки)
7. [Развёртывание](#развёртывание)
8. [Решение проблем](#решение-проблем)

## Обзор

Реализована полная система поддержки QuickOffer с двумя режимами обработки:

- **Режим A:** 6 детерминированных автоматических потоков с валидацией и одобрением
- **Режим B:** RAG-исследование с LLM синтезом и автоматической эскалацией

**Готовые потоки Режима A:**
- **Флоу 4:** Получение реферального промокода (15% скидка, бессрочный)
- **Флоу 5:** Получение промокода за отзыв (15% скидка, одноразовый)
- **Другие:** Возврат, архивирование вакансий, крипто-платежи, помощь в карьере

**Ключевые возможности:**
- ✅ 6 детерминированных потоков (Режим A) с одобрением персонала
- ✅ RAG-retrieval с гибридным поиском (BM25 + семантический)
- ✅ Автоматические эскалации (7 триггеров)
- ✅ Система оценки качества (бенчмарк, confidence scoring)
- ✅ Полная изоляция LLM (только чтение данных)
- ✅ Полный audit trail для соответствия нормативам

## Архитектура двойного режима

### Общий поток обработки

```
Вопрос пользователя
       ↓
  ФАЗА 1: Классификация интента (MODE_A vs MODE_B)
       ↓
  ┌─────────────────┬──────────────────┐
  ↓                 ↓
РЕЖИМ A          РЕЖИМ B
(6 потоков)      (RAG + LLM)
  ↓                 ↓
ФАЗА 2:        ФАЗА 2:
Инициализация  RAG Retrieval
FSM            (гибридный поиск)
  ↓                 ↓
ФАЗА 3:        ФАЗА 3:
Выполнение     LLM Генерация
инструментов   (read-only)
  ↓                 ↓
ФАЗА 4:        ФАЗА 4:
Ответ или      Ответ или
Одобрение      Эскалация
```

### Режим A vs Режим B

| Аспект | Режим A (Детерминированный) | Режим B (Исследование) |
|--------|---------------------------|----------------------|
| **Типы вопросов** | 6 предопределенных потоков | Все остальные вопросы |
| **Обработка** | Конечный автомат (FSM) | RAG + LLM синтез |
| **Одобрение** | Требуется для рискованных операций | Нет (только читает) |
| **Инструменты** | Мутирующие API вызовы | Только read-only |
| **Скорость** | Быстро (~1-2 сек) | Медленнее (~5-10 сек) |
| **Погрешность** | ~0% (детерминирован) | ~5-15% (LLM риск) |

## Что было реализовано

### 1. FuckHR Support API Client

**Файл:** `src/infrastructure/m2m/fuckhr_client.py`

HTTP-клиент для интеграции с FuckHR API поддерживающий:

```python
class FuckHRSupportAPIClient:
    # Проверка привязки Telegram ID к QuickOffer аккаунту
    async def check_identity(telegram_id: int) -> dict
    
    # Генерация одноразовой auth-ссылки для привязки
    async def generate_auth_link(telegram_id: int, ttl_seconds: int = 3600) -> dict
    
    # Получение/создание реферального промокода
    async def get_referral_promo_code(user_id: str) -> dict
    
    # Проверка наличия отзыва пользователя
    async def check_review(user_id: str) -> dict
    
    # Получение/создание промокода за отзыв
    async def get_review_promo_code(user_id: str) -> dict
    
    # Получение URL формы для добавления отзыва
    async def get_review_form_url() -> dict
```

**Ключевые особенности:**
- ✅ Автоматическая подставка заголовков `Idempotency-Key` и `Trace-ID`
- ✅ Обработка HTTP ошибок с кастомным исключением `FuckHRSupportAPIError`
- ✅ Structured logging для отладки и мониторинга
- ✅ Поддержка async/await для неблокирующих операций

### 2. Identity Service (Сервис привязки личности)

**Файл:** `src/services/identity.py`

Сервис управления привязкой аккаунтов Telegram к QuickOffer:

```python
class IdentityService:
    # Проверить привязку Telegram ID
    async def check_identity(telegram_id: int) -> IdentityCheckResponse
    
    # Создать одноразовую auth-ссылку
    async def generate_auth_link(telegram_id: int, ttl_seconds: int = 3600) -> AuthLinkResponse
    
    # Проверить привязку или создать auth-ссылку
    async def check_and_bind_or_link(telegram_id: int) -> dict
```

**Pydantic модели:**
- `IdentityCheckResponse` - результат проверки привязки
- `AuthLinkResponse` - результат создания auth-ссылки

### 3. Database Models

#### ReferralOwnershipMapping

Таблица для отслеживания реферальных кодов каждого пользователя:

```sql
CREATE TABLE referral_ownership_mappings (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE,          -- QuickOffer user ID
    promo_code VARCHAR(50) UNIQUE,        -- 15% промокод
    discount_percent INTEGER DEFAULT 15, -- Всегда 15%
    is_active BOOLEAN DEFAULT TRUE,       -- Флаг активности
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

**Назначение:** Один код на пользователя, бессрочный, с возможностью отслеживания владельца.

#### ReviewPromoCodeUsage

Таблица для отслеживания one-time промокодов за отзывы:

```sql
CREATE TABLE review_promo_code_usages (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),                 -- QuickOffer user ID
    review_id VARCHAR(255),               -- ID отзыва в FuckHR
    promo_code VARCHAR(50) UNIQUE,        -- One-time 15% код
    discount_percent INTEGER DEFAULT 15, -- Всегда 15%
    max_uses INTEGER DEFAULT 1,           -- Максимум 1 использование
    times_used INTEGER DEFAULT 0,         -- Счетчик использования
    is_active BOOLEAN DEFAULT TRUE,       -- Флаг активности
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

**Назначение:** Одноразовые коды, привязанные к пользователю и отзыву.

### 4. Миграции БД

**Migration 002:** `add_referral_ownership_mapping`
- Создание таблицы `referral_ownership_mappings`
- Индексы на: user_id, promo_code, is_active

**Migration 003:** `add_review_promo_code_usage`
- Создание таблицы `review_promo_code_usages`
- Индексы на: user_id, review_id, promo_code, is_active

### 5. Telegram Bot Flows

#### Флоу 4: Реферальный промокод

**Команда:** `/referral_code`

**FSM состояния:**
```
INITIAL
  ↓
requesting_code
  ↓
checking_identity
  ├→ not_bound: [отправляем auth-ссылку]
  │
  └→ bound:
      ↓
      generating_code
      ↓
      code_ready [отправляем код]
```

**Бизнес-логика:**
- Один реферальный код на один QuickOffer аккаунт
- Скидка: 15% (фиксированная)
- Действителен: Бесконечно (нет срока истечения)
- Проверка ownership через `ReferralOwnershipMapping`
- Если маппинг найден → возвращаем существующий код
- Если маппинг не найден → создаем новый код и маппинг

**Пример использования:**
```
Пользователь: /referral_code

Бот: 🎁 Получаем ваш реферальный код...
     Давайте сначала проверим ваш аккаунт QuickOffer

[Проверка привязки Telegram ID]

Бот: ✅ Аккаунт проверен!
     Генерируем ваш реферальный код...

🆕 Новый код создан!

📋 Реферальный код: `QUICKOFFER_ABC123_REF`
💰 Скидка: 15%
⏱️ Действителен: Навсегда

Поделитесь этим кодом с друзьями, и они получат 15% скидку!
```

#### Флоу 5: Промокод за отзыв

**Команда:** `/review_promo`

**FSM состояния:**
```
INITIAL
  ↓
requesting_code
  ↓
checking_identity
  ├→ not_bound: [отправляем auth-ссылку]
  │
  └→ bound:
      ↓
      checking_review
      ├→ review_not_found:
      │   ↓
      │   sending_form [отправляем ссылку на форму]
      │
      └→ review_found:
          ↓
          generating_code
          ↓
          code_ready [отправляем код]
```

**Бизнес-логика:**
- Проверяет наличие опубликованного отзыва (минимум 30 символов)
- Принимает отзывы с любым sentiment (положительные, нейтральные, отрицательные)
- Учитывает edge case: фронтенд показывает "Отзыв опубликован", но бэкенд сохраняет Published=false
- Если отзыва нет → отправляет ссылку на форму сбора отзывов
- Если отзыв уже выдан код → возвращает существующий
- Если отзыва нет, но он написан → создает безопасный одноразовый промокод

**Код:**
- One-time использование (max_uses = 1)
- Привязан к пользователю (user-bound)
- Скидка: 15% (фиксированная)
- Действителен: Бесконечно (но используется только 1 раз)

**Пример использования (есть отзыв):**
```
Пользователь: /review_promo

Бот: ⭐ Получаем промокод за ваш отзыв!
     Давайте сначала проверим ваш аккаунт QuickOffer

[Проверка привязки]

Бот: ✅ Аккаунт проверен!
     Проверяем ваши отзывы...

🎉 Мы нашли ваш отзыв!
Генерируем ваш промокод...

🆕 Новый код создан!

📋 Промокод: `QUICKOFFER_XYZ789_REV`
💰 Скидка: 15%
📌 Использований: 1 (одноразовый)
👤 Привязан к аккаунту: Да

Этот код исключительно для вас и может быть использован только один раз.
Спасибо за ваш отзыв!
```

**Пример использования (нет отзыва):**
```
Пользователь: /review_promo

[Проверка Telegram ID]

Бот: ✅ Аккаунт проверен!
     Проверяем ваши отзывы...

📝 Мы еще не нашли ваш отзыв.

Пожалуйста, поделитесь вашим мнением по этой ссылке:

[ссылка_на_форму_отзыва]

📌 Примечание: После отправки ваш отзыв будет обработан.
Тогда вы сможете запросить промокод снова!
```

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│  Telegram Bot (aiogram v3)                              │
│                                                         │
│  /start, /help, /issue, /status, /cancel (основные)    │
│  /referral_code (Флоу 4)                                │
│  /review_promo (Флоу 5)                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Identity Service (src/services/identity.py)            │
│                                                         │
│  • Проверка привязки Telegram → QuickOffer              │
│  • Генерация одноразовых auth-ссылок                    │
│  • Управление жизненным циклом привязки                │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  FuckHR Support API Client                              │
│  (src/infrastructure/m2m/fuckhr_client.py)              │
│                                                         │
│  Endpoint: /internal/support/v1                         │
│  Headers: Idempotency-Key, Trace-ID                     │
│                                                         │
│  POST /identity/check                                   │
│  POST /identity/auth-link                               │
│  POST /promocodes/referral                              │
│  POST /reviews/check                                    │
│  POST /promocodes/review                                │
│  GET  /reviews/form-url                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │  FuckHR Backend API      │
        │  (fuckhr-api:8001)       │
        └──────────────────────────┘
```

## Быстрый старт

### Шаг 1: Применить миграции

```bash
# Применить все pending миграции к БД
alembic upgrade head

# Проверить статус
alembic current
```

### Шаг 2: Зарегистрировать Telegram маршруты

Обновите инициализацию бота (обычно в `main.py` или в startup):

```python
from src.presentation.telegram import (
    router,
    referral_router,
    review_router,
)

# В настройке dispatcher:
dp.include_router(router)              # Основные обработчики
dp.include_router(referral_router)     # Флоу 4
dp.include_router(review_router)       # Флоу 5
```

### Шаг 3: Проверить конфигурацию

Убедитесь, что `.env` содержит:

```env
# FuckHR API
FUCKHR_API_BASE_URL=http://fuckhr-api:8001
M2M_API_KEY=your-secret-api-key

# База данных
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/support_bot

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_APPROVAL_CHAT_ID=123456789
```

### Шаг 4: Запустить бота

```bash
# Через uvicorn
python -m uvicorn main:app --reload

# Или через docker-compose
docker-compose up -d
```

## API контракты

### FuckHR API Endpoints

#### POST /identity/check

**Запрос:**
```http
POST /internal/support/v1/identity/check HTTP/1.1
Authorization: Bearer {M2M_API_KEY}
Idempotency-Key: {uuid}
Trace-ID: {uuid}
Content-Type: application/json

{
  "telegram_id": 123456789
}
```

**Ответ (200 OK):**
```json
{
  "is_bound": true,
  "user_id": "user_abc123",
  "bound_at": "2026-08-19T12:53:00Z"
}
```

#### POST /identity/auth-link

**Запрос:**
```http
POST /internal/support/v1/identity/auth-link HTTP/1.1
Authorization: Bearer {M2M_API_KEY}
Idempotency-Key: {uuid}
Trace-ID: {uuid}
Content-Type: application/json

{
  "telegram_id": 123456789,
  "ttl_seconds": 3600
}
```

**Ответ (200 OK):**
```json
{
  "auth_url": "https://quickoffer.com/auth?token=abc123&expires=1234567890",
  "expires_at": "2026-08-19T13:53:00Z"
}
```

#### POST /promocodes/referral

**Запрос:**
```http
POST /internal/support/v1/promocodes/referral HTTP/1.1
Authorization: Bearer {M2M_API_KEY}
Idempotency-Key: {uuid}
Trace-ID: {uuid}
Content-Type: application/json

{
  "user_id": "user_abc123"
}
```

**Ответ (200 OK):**
```json
{
  "code": "QUICKOFFER_ABC123_REF",
  "discount_percent": 15,
  "expires_at": null,
  "is_new": false
}
```

#### POST /reviews/check

**Запрос:**
```http
POST /internal/support/v1/reviews/check HTTP/1.1
Authorization: Bearer {M2M_API_KEY}
Idempotency-Key: {uuid}
Trace-ID: {uuid}
Content-Type: application/json

{
  "user_id": "user_abc123"
}
```

**Ответ (200 OK, есть отзыв):**
```json
{
  "review_found": true,
  "review_id": "review_xyz789",
  "review_text": "Отличный сервис! Я очень доволен качеством...",
  "review_length": 150
}
```

**Ответ (200 OK, нет отзыва):**
```json
{
  "review_found": false,
  "review_id": null,
  "review_text": null,
  "review_length": 0
}
```

#### POST /promocodes/review

**Запрос:**
```http
POST /internal/support/v1/promocodes/review HTTP/1.1
Authorization: Bearer {M2M_API_KEY}
Idempotency-Key: {uuid}
Trace-ID: {uuid}
Content-Type: application/json

{
  "user_id": "user_abc123"
}
```

**Ответ (200 OK):**
```json
{
  "code": "QUICKOFFER_XYZ789_REV",
  "discount_percent": 15,
  "max_uses": 1,
  "user_bound": true,
  "is_new": true,
  "review_id": "review_xyz789"
}
```

#### GET /reviews/form-url

**Запрос:**
```http
GET /internal/support/v1/reviews/form-url HTTP/1.1
Authorization: Bearer {M2M_API_KEY}
Trace-ID: {uuid}
```

**Ответ (200 OK):**
```json
{
  "review_form_url": "https://quickoffer.com/reviews/form"
}
```

## Тестирование

### Ручное тестирование в Telegram

```
/help              # Показать все команды
/referral_code     # Тест Флоу 4
/review_promo      # Тест Флоу 5
/cancel            # Отменить текущую операцию
```

### Модульные тесты

```python
import pytest
from unittest.mock import AsyncMock
from src.infrastructure.m2m.fuckhr_client import FuckHRSupportAPIClient

@pytest.mark.asyncio
async def test_check_identity():
    client = FuckHRSupportAPIClient()
    client.check_identity = AsyncMock(
        return_value={"is_bound": True, "user_id": "test_user"}
    )
    
    result = await client.check_identity(123456789)
    assert result["is_bound"] is True
    assert result["user_id"] == "test_user"

@pytest.mark.asyncio
async def test_generate_auth_link():
    client = FuckHRSupportAPIClient()
    client.generate_auth_link = AsyncMock(
        return_value={
            "auth_url": "https://test.com/auth?token=abc",
            "expires_at": "2026-08-19T13:53:00Z"
        }
    )
    
    result = await client.generate_auth_link(123456789)
    assert "auth_url" in result
    assert "expires_at" in result
```

### Интеграционные тесты

```bash
# Протестировать с реальным FuckHR API (если доступен)
pytest tests/integration/ -v

# Протестировать с mock FuckHR API
pytest tests/integration/ -v --mock-api
```

## Решение проблем

### Проблема: Бот не отвечает на `/referral_code`

**Решение:**
1. Проверьте, что маршруты зарегистрированы:
   ```python
   dp.include_router(referral_router)
   ```
2. Проверьте токен Telegram в `.env`
3. Посмотрите логи: `docker logs bot` или `docker-compose logs bot`

### Проблема: Ошибка при проверке личности

**Решение:**
1. Проверьте, что FuckHR API запущен:
   ```bash
   curl http://localhost:8001/health
   ```
2. Проверьте `M2M_API_KEY` в `.env`
3. Посмотрите детали ошибки в логах

### Проблема: Миграция БД не применяется

**Решение:**
1. Проверьте, что БД запущена:
   ```bash
   docker logs postgres
   ```
2. Проверьте `DATABASE_URL` в `.env`
3. Проверьте синтаксис миграции:
   ```bash
   cat migrations/versions/002_*.py
   ```

### Проблема: Timeout при генерации промокода

**Решение:**
1. Проверьте производительность FuckHR API
2. Проверьте сетевое соединение
3. Увеличьте timeout в `FuckHRSupportAPIClient._make_request()`

## Качество кода

### Проверка перед коммитом

```bash
# Type checking
mypy src/ --strict

# Code formatting
black src/ --line-length 88

# Import sorting
isort src/ --profile black

# Linting (опционально)
pylint src/
flake8 src/
```

### Стандарты соответствия

✅ **Type Safety:** 100% типизирован (mypy compliant)
✅ **Code Style:** Black formatted (88 символов в строке)
✅ **Imports:** isort организованы
✅ **Documentation:** Полные docstring'и
✅ **Error Handling:** Кастомные исключения, graceful fallback
✅ **Logging:** Structured logging везде
✅ **Async/Await:** Консистентная async реализация
✅ **Pydantic:** Strict validation на всех input'ах
✅ **DRY:** Нет дублирования кода
✅ **SOLID:** Clean Architecture принципы

## Документация

- **IMPLEMENTATION.md** - Подробный технический гайд (500+ строк)
- **FILES_SUMMARY.md** - Файл-за-файлом разбор
- **QUICKSTART.md** - Quick reference для быстрого старта
- **README_RU.md** - Этот файл (русская документация)
- **README.md** - Оригинальная документация проекта

## Поддержка

Для вопросов и проблем:

1. Посмотрите **IMPLEMENTATION.md** для подробной информации
2. Проверьте логи: `docker logs bot`
3. Проверьте конфигурацию в `.env`
4. Протестируйте FuckHR API напрямую через curl/Postman

## Резюме

### Реализовано:

✅ Надежная интеграция с FuckHR Support API
✅ Сервис привязки личности для Telegram пользователей
✅ Два готовых к использованию детерминированных флоу
✅ ORM модели для персистентности
✅ Правильная обработка ошибок и логирование
✅ Полная типизация и качество кода
✅ Clean Architecture с четким разделением ответственности
✅ Async/await везде
✅ Database migrations

### Статистика:

| Метрика | Значение |
|---------|----------|
| Новых Python файлов | 3 |
| Новых миграций | 2 |
| Новых документов | 3 |
| Строк нового кода | ~1000 |
| API методов | 6 |
| FSM состояний | 10 |
| ORM моделей | 2 |
| Индексов БД | 7 |

### Следующие шаги:

1. ✅ Применить миграции: `alembic upgrade head`
2. ✅ Зарегистрировать маршруты в инициализации бота
3. ✅ Протестировать `/referral_code` команду
4. ✅ Протестировать `/review_promo` команду
5. ✅ Мониторить логи и отладить проблемы
6. ✅ Развернуть в production

---

**Система готова к развертыванию!** 🚀

Все компоненты созданы с соблюдением стандартов качества и могут быть сразу использованы в production среде.

---

## Режим A: Детерминированные потоки

### Staff Approval Engine (Механизм согласований со сотрудниками)

Детерминированные флоу с **Staff Approval Engine** для управления высокорисковыми мутациями:

```
INITIAL → GATHERING_INFO → ANALYZING → PROPOSING_SOLUTION
       ↓                                      ↓
    ESCALATED                     WAITING_APPROVAL
                                        ↓
                    (Проверка Staff) → EXECUTING_ACTION → RESOLVED
```

#### Ключевые возможности:

✅ **Frozen Parameters** - Неизменяемые снимки действий с SHA256 хешированием
✅ **Auto-Invalidation** - Изменение параметров автоматически отклоняет одобрение
✅ **M2M Idempotency** - Все внешние вызовы включают `Idempotency-Key` + `Trace-ID` заголовки
✅ **Reconciliation Handling** - Успех провайдера + локальный отказ → `reconciliation_pending`
✅ **Staff Roles** - support, finance, admin с проверкой прав доступа
✅ **Telegram UI** - Inline карточки одобрения с кнопками approve/reject/info

#### Реализованные Flows:

**Flow 1: Возврат платежа и удаление подписки**
- Пользователь запрашивает возврат с доказательствами
- Бэкенд валидирует основания возврата (услуга не началась, двойное списание и т.д.)
- Карточка одобрения отправляется в чат сотрудников с frozen параметрами
- Сотрудник одобряет → вручную делает refund в YooKassa
- Бэкенд верифицирует refund → soft-удаляет подписку (деактивирует поиски, останавливает runs)
- Обработка reconciliation если провайдер успел, но локальное удаление упало

**Flow 3: Архивация вакансии**
- Пользователь запрашивает постоянную блокировку вакансии
- Сбор типа заявителя (работодатель/правообладатель/кандидат)
- Сбор основания и доказательств
- Карточка одобрения отправляется сотрудникам
- Сотрудник одобряет → M2M вызов к Jobs API с persistent suppression metadata
- Предотвращает переиндексацию парсером и запрещает реактивацию

**Подробная документация:**
См. [STAFF_APPROVAL_GUIDE.md](STAFF_APPROVAL_GUIDE.md) для всех деталей реализации, конфигурации и сценариев тестирования.

---

### Другие Flows (Флоу 4 и 5):

Смотрите выше подробное описание:
- **Флоу 4:** Реферальный промокод
- **Флоу 5:** Промокод за отзыв

---

## Полный список сервисов

### 1. FSM Service (`src/services/fsm.py`)
Finite State Machine для управления детерминированными потоками с проверкой переходов.

```python
from src.services.fsm import SupportFlowFSM

fsm = SupportFlowFSM()
can_proceed = fsm.can_transition(current_state, next_state)
fsm.transition(current_state, next_state, context)
allowed = fsm.get_allowed_transitions(current_state)
```

### 2. Identity Service (`src/services/identity.py`)
Управление привязкой аккаунтов Telegram к QuickOffer.

```python
from src.services.identity import get_identity_service

identity = get_identity_service()

# Проверить привязку
response = await identity.check_identity(telegram_id)

# Создать одноразовую auth-ссылку
auth_link = await identity.generate_auth_link(telegram_id, ttl_seconds=3600)

# Проверить или создать ссылку
result = await identity.check_and_bind_or_link(telegram_id)
```

### 3. Approval Service (`src/services/approval_service.py`)
Управление высокорисковыми действиями с frozen параметрами и проверкой целостности.

```python
from src.services.approval_service import ApprovalService

approval = ApprovalService()

# Создать действие с frozen параметрами
action = await approval.create_support_action(
    ticket_id=ticket_uuid,
    action_type="refund",
    params={"amount": 1000, "currency": "RUB"},
    risk_level="high"
)

# Проверить целостность параметров
is_valid = await approval.validate_params_integrity(action_id)

# Обработать решение одобрения
result = await approval.process_approval_decision(
    action_id=action_id,
    staff_id="staff_123",
    approved=True
)
```

### 4. Staff Approval Engine (`src/services/staff_approval.py`)
Управление одобрениями с учетом ролей сотрудников.

```python
from src.services.staff_approval import StaffApprovalEngine, StaffRole

staff_engine = StaffApprovalEngine()

# Добавить сотрудника
staff_engine.add_staff_member(
    staff_id="emp_123",
    roles=[StaffRole.SUPPORT, StaffRole.FINANCE]
)

# Проверить права одобрения
can_approve = staff_engine.can_approve(
    staff_id="emp_123",
    required_role=StaffRole.FINANCE
)

# Создать карточку одобрения
card = staff_engine.create_approval_card(
    action_id=action_uuid,
    action_type="refund",
    risk_level="high",
    params={"amount": 1000}
)

message = card.generate_message()
```

**Роли сотрудников:**
- `SUPPORT` - Может одобрять действия low/medium risk
- `FINANCE` - Требуется для финансовых действий
- `ADMIN` - Может одобрять все действия, включая critical

### 5. LLM Service (`src/services/llm.py`)
**Read-only** LLM интеграция с поддержкой OpenAI и Anthropic.

```python
from src.services.llm import get_llm_service

llm = get_llm_service()

# Только read-only операции
response = await llm.generate_response(prompt)
analysis = await llm.analyze_ticket(content)
suggestion = await llm.suggest_resolution(ticket_id)
```

**Поддерживаемые провайдеры:**
- OpenAI: `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`
- Anthropic: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`

### 6. RAG Investigation Service (`src/services/llm_investigation.py`)
Retrieval-Augmented Generation для расследования вопросов через Knowledge Base.

```python
from src.services.llm_investigation import InvestigationService

investigation = InvestigationService()

# Расследовать вопрос
result = await investigation.investigate(
    query="Как сбросить пароль?",
    user_id="user_123",
    conversation_context={"verified": True}
)

# Зарегистрировать версию KB
investigation.register_kb_version(
    kb_id="faq_main",
    owner="support_team",
    version="1.0.0",
    status="active",
    effective_date=datetime.now(),
    review_date=datetime(2026, 12, 31)
)
```

**Фильтрация KB:**
- ✅ Только `"active"` KB используются
- ❌ `"draft"` и `"archived"` исключаются
- ✅ Проверка дат: `effective_date <= now <= review_date`

### 7. Handoff Engine (`src/services/handoff_engine.py`)
Автоматическая эскалация на человека с 7 триггерами.

```python
from src.services.handoff_engine import get_handoff_service, HandoffTriggerType

handoff = get_handoff_service()

# Проверить и выполнить handoff если нужен
context = HandoffContext(
    conversation_id=conv_id,
    user_id="user_123",
    trigger_type=HandoffTriggerType.EXPLICIT_REQUEST,
    trigger_reason="Пользователь попросил оператора"
)

is_handed_off = await handoff.check_and_execute(context)

# Отслеживать сбои для обнаружения каскадов
handoff.record_tool_failure(conversation_id)
handoff.record_llm_failure(conversation_id)
handoff.reset_failures(conversation_id)
```

**7 триггеров escalation:**
1. `EXPLICIT_REQUEST` - Явный запрос ("оператора", "менеджер")
2. `IDENTITY_NOT_VERIFIED` - Проверка идентичности не прошла
3. `MONEY_LEGAL_ISSUE` - Финансовые/юридические вопросы
4. `ACCOUNT_SECURITY` - Взлом/безопасность аккаунта
5. `DATA_REQUEST_UNKNOWN_POLICY` - GDPR/удаление данных
6. `TOOL_FAILURE_CASCADE` - 2+ ошибки инструмента подряд
7. `DOUBLE_LLM_FAILURE` - 2+ ошибки LLM подряд

### 8. Read-Only Tools Registry (`src/services/llm_tools.py`)
Строго контролируемый набор read-only инструментов для LLM.

```python
from src.services.llm_tools import get_tools_registry

tools = get_tools_registry()

# Получить доступные инструменты
available = tools.get_available_tools()

# Выполнить инструмент
result = await tools.execute_tool("faq", query="Как сбросить пароль?")
```

**Доступные инструменты:**
- `ApprovedFAQTool` - FAQ из curated KB
- `UserSupportSnapshotTool` - История поддержки пользователя
- `SubscriptionStatusTool` - Статус подписки
- `MaskedPaymentsTool` - Маскированная история платежей
- `SearchHealthTool` - Здоровье сервиса поиска
- `CurrentIncidentsTool` - Текущие инциденты
- `PromoEligibilityTool` - Eligibility для промокодов
- `JobsPublicStatusTool` - Публичный статус вакансий

**Физическая изоляция:**
- ❌ БЕЗ mutation tools
- ❌ БЕЗ raw SQL
- ❌ БЕЗ shell access
- ✅ ТОЛЬКО read-only операции

---



## Режим B: LLM расследование и Human Handoff

### 📌 Обзор

Режим B обеспечивает ответы на вопросы, которые не подходят для детерминированных Режима A флоу. Использует RAG-базированное расследование с автоматической передачей человеку при наличии рисков.

### 🏗️ Компоненты

#### 1. RAG Investigation Service (`src/services/llm_investigation.py`)

Сервис для расследования общих вопросов через Retrieval-Augmented Generation:

```python
class InvestigationService:
    async def investigate(
        query: str,
        user_id: str | None = None,
        conversation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Расследование вопроса через RAG:
        1. Классификация запроса (public/authenticated)
        2. Получение из Knowledge Base
        3. Генерация ответа LLM
        4. Валидация уверенности
        """
```

**Ключевые особенности:**
- ✅ Версионирование Knowledge Base (owner, version, effective_date, review_date)
- ✅ Фильтрация по статусу KB (active только)
- ✅ Классификация доступа (public/authenticated)
- ✅ Минимальный retrieval с сортировкой по релевантности
- ✅ LLM анализ с проверкой конфиденциальности

#### 2. Read-Only Tools Registry (`src/services/llm_tools.py`)

Строго контролируемый набор read-only инструментов для LLM:

```python
ApprovedFAQTool()              # FAQ из curated KB
UserSupportSnapshotTool()      # История поддержки пользователя
SubscriptionStatusTool()       # Статус подписки
MaskedPaymentsTool()           # Маскированная история платежей
SearchHealthTool()             # Здоровье поиска
CurrentIncidentsTool()         # Текущие инциденты
PromoEligibilityTool()         # Eligibility для промокодов
JobsPublicStatusTool()         # Публичный статус вакансий
```

**Физическая изоляция:**
- ❌ NO mutation tools
- ❌ NO raw SQL
- ❌ NO shell access
- ❌ NO arbitrary HTTP
- ✅ ONLY read-only operations

#### 3. Human Handoff Engine (`src/services/handoff_engine.py`)

Механизм автоматической эскалации на человека с 7 триггерами:

```python
class HandoffTriggerType(str, Enum):
    EXPLICIT_REQUEST = "explicit_request"                    # Клиент просит человека
    IDENTITY_NOT_VERIFIED = "identity_not_verified"          # Identity не подтверждена
    MONEY_LEGAL_ISSUE = "money_legal_issue"                  # Вопросы про деньги/право
    ACCOUNT_SECURITY = "account_security"                    # Account takeover/безопасность
    DATA_REQUEST_UNKNOWN_POLICY = "data_request_unknown_policy"  # Запрос чужих данных
    TOOL_FAILURE_CASCADE = "tool_failure_cascade"             # Повторный сбой инструмента
    DOUBLE_LLM_FAILURE = "double_llm_failure"                 # Два неуспешных ответа LLM
```

#### 4. Database Models

**KnowledgeBaseVersion:**
```python
kb_id: str                      # ID knowledge base
owner: str                      # Owner/maintainer
version: str                    # Version number
status: str                     # active|draft|archived
effective_date: datetime        # Date KB becomes active
review_date: datetime           # Date KB review expires
content_hash: str               # SHA256 hash for integrity
```

**HandoffTicket:**
```python
conversation_id: UUID           # FK к conversation
user_id: str                    # User identifier
trigger_type: str               # Type of escalation
trigger_reason: str             # Detailed reason
status: str                     # created|notified|assigned|...
investigation_summary: str      # Context for operator
confidence_score: float         # Investigation confidence
assigned_to: str | None         # Assigned operator
```

**CollectedFact:**
```python
handoff_ticket_id: UUID         # FK к handoff ticket
fact_type: str                  # user_message|tool_failure|llm_error
source: str                     # user_input|investigation_service|...
value: str                      # Fact value
confidence: float               # Confidence score
```

### 🔄 Flow диаграмма Mode B

```
User Message (вопрос вне Mode A)
    ↓
[1] Detect Handoff Trigger? → Yes → [HANDOFF MODE]
    ↓ No
[2] RAG Investigation
    • Classify (public/authenticated)
    • Retrieve from KB (filtered by version)
    • Score entries
    ↓
[3] LLM Analysis
    • Read-only tools only
    • Generate response with context
    ↓
[4] Policy Check & Validation
    • Confidence > threshold?
    • Policy compliant?
    ↓ Low confidence / Policy violation → HANDOFF
    ↓ Success
[5] Send Response
    ↓
[6] Log Fact + Check Triggers
    ↓
[7] Close or Escalate
```

### 🚨 Семь триггеров Human Handoff

#### 1️⃣ **Explicit Request** (Явный запрос человека)

Ключевые слова: `"human"`, `"operator"`, `"manager"`, `"к человеку"`, `"оператора"`

```
Пользователь: "Подключите меня к оператору"
→ Handoff: IMMEDIATE
```

#### 2️⃣ **Identity Not Verified** (Идентичность не подтверждена)

Срабатывает, если пользователь не прошел проверку идентичности.

```
Context: {identity_verified: false}
→ Handoff: IMMEDIATE
```

#### 3️⃣ **Money/Legal Issue** (Финансовые/Юридические вопросы)

Ключевые слова: `"refund"`, `"chargeback"`, `"lawsuit"`, `"возврат"`, `"судебное"`

```
Пользователь: "Хочу вернуть деньги за заказ"
→ Handoff: IMMEDIATE
```

#### 4️⃣ **Account Security** (Безопасность счета)

Ключевые слова: `"hacked"`, `"breached"`, `"взломана"`, `"не мой счет"`

```
Пользователь: "Мой аккаунт взломан!"
→ Handoff: IMMEDIATE
```

#### 5️⃣ **Data Request/Unknown Policy** (Запрос данных/Неизвестная политика)

Ключевые слова: `"export data"`, `"GDPR"`, `"delete account"`, `"данные"`

```
Пользователь: "Удалите все мои данные"
→ Handoff: IMMEDIATE
```

#### 6️⃣ **Tool Failure Cascade** (Повторный сбой инструмента)

Срабатывает при 2+ последовательных сбоев инструмента.

```
Context: {tool_failure_count: 2}
→ Handoff: IMMEDIATE
```

#### 7️⃣ **Double LLM Failure** (Два неудачных ответа LLM)

Срабатывает при 2+ последовательных ошибок генерации LLM.

```
Context: {llm_failure_count: 2}
→ Handoff: IMMEDIATE
```

### 📊 Knowledge Base Management

#### KB Versioning

Каждая версия KB должна иметь:

```python
{
    "kb_id": "faq_main",
    "owner": "support_team",
    "version": "1.2.3",
    "status": "active",                    # active|draft|archived
    "effective_date": "2026-08-19",        # When KB becomes active
    "review_date": "2026-12-31",          # When KB review expires
    "content_hash": "abc123..."            # SHA256 of content
}
```

#### Validation Rules

```
✅ INCLUDE:  status == "active"
✅ INCLUDE:  effective_date <= NOW
✅ INCLUDE:  review_date >= NOW
❌ EXCLUDE:  status == "draft"
❌ EXCLUDE:  status == "archived"
❌ EXCLUDE:  effective_date > NOW
❌ EXCLUDE:  review_date < NOW
```

#### Classification Rules

```
PUBLIC:
  - FAQ entries
  - General information
  - Public announcements

AUTHENTICATED:
  - Account information
  - Personal settings
  - User-specific content
```

### 🔧 Configuration

Добавьте в `.env`:

```env
# RAG Configuration (Mode B)
RAG_KB_BASE_URL=http://localhost:8003
RAG_MAX_RETRIEVAL_COUNT=5
RAG_CONFIDENCE_THRESHOLD=0.7

# Handoff Configuration
HANDOFF_TIMEOUT_MINUTES=120
HANDOFF_FACTS_RETENTION_DAYS=30
```

### 📝 Интеграция с Telegram Handler

```python
from src.presentation.telegram.mode_b_handlers import handle_mode_b_question

# В инициализации бота:
router.message.register(
    handle_mode_b_question,
    StateFilter(None),  # Нет активного FSM state
    # Регулярное сообщение, не команда
)
```

### 📤 Handoff Notification для админов

При срабатывании handoff создается сообщение в admin chat:

```
🚨 Human Handoff Triggered

Ticket ID: 550e8400-e29b-41d4-a716-446655440000
User ID: user_abc123
Conversation ID: 123456789

Trigger Type: money_legal_issue
Reason: Message contains money, chargeback, or legal keywords

Investigation Summary:
Investigation confidence: 0.65. Reason: low_confidence

Collected Facts:
  • [user_message] User wants a refund
  • [tool_failure] Tool failed 2 times
  
Recent Messages:
  user: I want a refund...
  bot: I can help you...
  user: This is not acceptable...

Confidence Score: 0.65
Timestamp: 2026-08-19T13:42:00Z
```

## LLM Improver: Улучшение ответов с RAG-контекстом

### 🎯 Компонент `src/benchmarking/llm_improver.py`

Расширенная система улучшения ответов с интеллектуальным отслеживанием RAG-контекста и контролем тона:

#### 📌 Ключевые особенности:


## Тестирование и бенчмарки

### Unit & Integration тесты

```bash
# Запустить все тесты
pytest tests/

# С отчетом о покрытии
pytest --cov=src tests/

# Специфичные тесты (эскалация Mode B)
pytest tests/test_handoff_triggers.py -v
```

### Система оценки качества (Benchmarking)

```bash
# Запустить полный бенчмарк (10 тестовых вопросов)
python -m src.benchmarking.benchmark

# Интерактивная демонстрация (Режим A & B)
python -m src.benchmarking.interactive_demo
```

**Отслеживаемые метрики:**
- Точность классификации интента (MODE_A vs MODE_B)
- Качество RAG retrieval (BM25 + semantic + rerank)
- Качество LLM ответов
- Распределение confidence scores
- Разбор по этапам обработки

**Вывод:** `benchmark_results.json` с детальным анализом

### Покрытие тестами

- ✅ Переходы конечного автомата Режима A
- ✅ RAG retrieval и LLM генерация Режима B
- ✅ Все 7 сценариев триггеров эскалации
- ✅ Workflow одобрения и frozen параметры
- ✅ Обработка ошибок M2M API
- ✅ Версионирование Knowledge Base и фильтрация
- ✅ Binding личности и auth flow

## Развёртывание

### Подготовка

1. **Создать `.env` файл** из `.env.example`:
```bash
cp .env.example .env
# Отредактировать с вашими значениями
```

2. **Установить зависимости**:
```bash
pip install -e .
```

3. **Инициализировать БД**:
```bash
alembic upgrade head
```

4. **Загрузить Knowledge Base версию** для Режима B:
```python
from src.services.llm_investigation import InvestigationService
from datetime import datetime, timedelta

service = InvestigationService()
service.register_kb_version(
    kb_id="faq_main",
    owner="support_team",
    version="1.0.0",
    entries=[...],  # Вашим данными KB
    effective_date=datetime.utcnow(),
    review_date=datetime.utcnow() + timedelta(days=90)
)
```

### Локальная разработка (Mock режим)

```bash
# Выставить USE_MOCKS=true в .env
USE_MOCKS=true

# Запустить бота
python run_bot.py
```

Mock клиенты симулируют реальные API ответы для всех M2M операций.

### Production развёртывание

```bash
# Используя Docker Compose
docker-compose up -d

# Проверить статус
docker-compose ps

# Просмотреть логи
docker-compose logs -f bot
```

### Мониторинг

**Ключевые метрики для мониторинга:**
- `handoff_tickets_created_total` - Общее количество эскалаций
- `handoff_triggers_by_type` - Распределение по типам триггеров
- `investigation_confidence_avg` - Средняя confidence для Mode B
- `investigation_duration_seconds` - Время исследования
- `llm_failures_total` - Ошибки LLM
- `tool_failures_total` - Ошибки инструментов

## Документация

Дополнительная документация по различным аспектам:

| Документ | Назначение |
|----------|-----------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Полная архитектура (4 фазы, потоки, инструменты) |
| **[BENCHMARK_README.md](BENCHMARK_README.md)** | Система бенчмаркинга и метрики QA |
| **[RAG_AND_LLM_IMPROVEMENTS.md](RAG_AND_LLM_IMPROVEMENTS.md)** | Улучшения семантического поиска и LLM |
| **[SYSTEM_PROMPTS_UPDATE.md](SYSTEM_PROMPTS_UPDATE.md)** | LLM системные промпты и терминология |
| **[FLOW_TERMINOLOGY.md](FLOW_TERMINOLOGY.md)** | Уточнение определений (flow vs mode vs phase) |

## Решение проблем

### Проблемы с подключением к БД

```bash
# Проверить статус БД
docker-compose ps

# Просмотреть логи БД
docker-compose logs postgres

# Сброс БД
docker-compose down -v
docker-compose up
```

### Бот не отвечает

```bash
# Проверить логи бота
docker-compose logs bot

# Проверить Telegram token
docker-compose exec bot python -c "from src.core.config import settings; print(settings.telegram_bot_token)"

# Проверить подключение к БД
docker-compose exec bot python -c "from src.infrastructure.db.session import get_session; import asyncio; asyncio.run(get_session())"
```

### Проблемы с RAG/LLM интеграцией

```bash
# Протестировать API эмбеддингов
docker-compose exec bot python -c "from src.benchmarking.hybrid_retriever import EmbeddingService; print(EmbeddingService().get_embedding('test'))"

# Запустить интерактивную демонстрацию
python -m src.benchmarking.interactive_demo

# Просмотреть результаты бенчмарка
cat benchmark_results.json | jq '.statistics'
```

### Проблемы с эскалацией Mode B

```bash
# Протестировать детектирование handoff
docker-compose exec bot python -c "
from src.services.handoff_engine import HandoffService
service = HandoffService()
print(service.detect_triggers('I want to delete my account'))
"

# Просмотреть логи эскалаций
docker-compose logs bot | grep "HANDOFF"
```

### Проверка Mock режима

```bash
# Убедиться что mock режим активен
grep "USE_MOCKS" .env

# Протестировать mock клиентов
python -c "
from src.infrastructure.m2m import get_fuckhr_client, get_jobs_client
fuckhr = get_fuckhr_client()
jobs = get_jobs_client()
print(f'FuckHR: {type(fuckhr).__name__}')
print(f'Jobs: {type(jobs).__name__}')
"
```

**1. Отслеживание RAG-контекста:**
- Явное указание типа источника (FAQ, история поддержки, документация, RAG/диалоги)
- Метаданные о контексте источника
- Видимость оценки уверенности в пользовательском промпте
- Проверки качества для верификации информации из базы знаний

**2. Контроль тона и стиля:**
- **Профессиональный, дружелюбный и неспешный тон** - подчеркивает заботу о клиентах
- **Простой язык** - избегает жаргона, объясняет сложные концепции ясно
- **Ориентированность на пользователя** - фокусируется на потребностях и удобстве
- **Краткость и полнота** - баланс между лаконичностью и информативностью
- **Мобильная дружественность** - короткие абзацы, четкие шаги, оптимизация для телефонов
- **Эмпатия и человечность** - признание эмоций, выражение готовности помочь

**3. Процесс синтеза ответов:**
- **Очистка** - удаление артефактов диалога, временных меток, разговорных выражений
- **Переформатирование** - преобразование в повелительный тон инструкций с нумерованными шагами
- **Верификация** - обеспечение соответствия политике QuickOffer
- **Профессиональное форматирование** - четкая структура с высокой читаемостью

#### 💻 Использование:

```python
from src.benchmarking.llm_improver import LLMImprover

improver = LLMImprover()

# Базовое использование (обратная совместимость)
improved, confidence = improver.improve_answer(
    question="Как сбросить пароль?",
    weak_answer="секундочку... нужно в приложение зайти...",
    confidence=0.5
)

# Продвинутое использование с RAG-контекстом
improved, confidence = improver.improve_answer(
    question="Как получить возврат?",
    weak_answer="Можно запросить возврат через поддержку",
    confidence=0.6,
    rag_context="Извлечено из FAQ раздела о политике возврата",
    source_type="FAQ"
)
```

#### 🔧 Особенности системного промпта:
- Определяет роль как агент поддержки QuickOffer
- Список 6 категорий поддержки
- Спецификация принципов тона с примерами (хорошо vs плохо)
- Рекомендации по эмпатии
- Критические правила безопасности (идентификация по Telegram ID, отсутствие прямых мутаций БД)

#### 📝 Особенности пользовательского промпта:
- Показывает источник информации с уровнем уверенности
- Отображает RAG-контекст, когда доступен
- Список задач синтеза с четкими шагами
- Чек-лист проверки качества
- Рекомендации по профессиональному форматированию

## Режим B: LLM расследование и эскалация

Для всех вопросов, которые не соответствуют 6 предопределенным потокам Режима A.

### Компоненты Режима B

1. **InvestigationService** (`src/services/llm_investigation.py`)
   - Классификация вопроса (уровень доступа: публичный/аутентифицированный)
   - Retrieval из Knowledge Base с версионированием
   - LLM синтез ответа (read-only операции)
   - Scoring уверенности

2. **HandoffService** (`src/services/handoff_engine.py`)
   - Мониторинг 7 триггеров эскалации
   - Создание escalation тикетов с frozen context
   - Уведомление команды поддержки с собранными фактами
   - Предотвращение утечки чувствительных данных

3. **HybridRetriever** (`src/benchmarking/hybrid_retriever.py`)
   - BM25 лексический поиск (30% вес)
   - Семантический поиск через FAISS эмбеддинги (70% вес)
   - Reranking результатов для релевантности
   - Graceful fallback при сбое API

### 7 Триггеров Эскалации

| # | Триггер | Признаки | Пример |
|----|---------|----------|--------|
| 1 | **Explicit Request** | Явный запрос оператора | "меньше оператору", "хочу поговорить с человеком" |
| 2 | **Identity Not Verified** | Проверка личности не пройдена | Неподтвержденный Telegram ID |
| 3 | **Money/Legal** | Деньги, возврат, судебные иски | "хочу вернуть деньги", "подам в суд" |
| 4 | **Account Security** | Взлом аккаунта, компромисс | "аккаунт взломан", "изменил пароль" |
| 5 | **Data Request** | GDPR, удаление, экспорт данных | "удалить мои данные", "GDPR запрос" |
| 6 | **Tool Failures** | 2+ каскадных сбоя инструментов | Два подряд неудачных API вызова |
| 7 | **LLM Failures** | 2+ подряд сбои LLM генерации | Два подряд неудачных LLM вызова |

### Knowledge Base Версионирование

Каждая версия KB имеет:
- **Owner & Version**: Явный учет ответственности
- **Effective/Review Dates**: Автоматическая активация/деактивация
- **Status Filtering**: Только "active" версии используются
- **Date Validation**: KB должна быть в эффективном периоде

**Фильтры:**
```
INCLUDE: status == "active"
INCLUDE: effective_date <= NOW <= review_date

EXCLUDE: status == "draft"
EXCLUDE: status == "archived"
EXCLUDE: effective_date > NOW
EXCLUDE: review_date < NOW
```

### Scoring Уверенности

Ответы LLM включают confidence уровни:
- **Very High (≥ 0.85)**: Дать ответ пользователю сразу
- **High (0.7-0.85)**: Дать ответ с примечанием о контексте
- **Medium (0.5-0.7)**: Попросить уточнение
- **Low (< 0.5)**: Эскалация на человека

### 🛠️ Исправления поиска и бенчмарка

Пайплайн извлечения в бенчмарке был проверён и исправлен:

- **Восстановлен семантический поиск**: `HybridRetriever.retrieve()` теперь
  вызывает FAISS-версию скоринга (`_compute_semantic_scores_faiss`). Ранее
  использовался полный перебор по пустому списку эмбеддингов (когда эмбеддинги
  берутся из FAISS-кэша), из-за чего `Semantic` был равен `0.0` для всех
  запросов.
- **Корректная косинусная метрика в FAISS**: эмбеддинги L2-нормализуются при
  построении индекса и при запросе, поэтому расстояние `IndexFlatL2` напрямую
  соответствует косинусному сходству. Устаревшие (ненормализованные) кэши
  определяются по флагу `normalized` и автоматически перестраиваются.
- **Флоу больше не перехватывают информационные вопросы**: LLM-матчер флоу
  принимает только высокоуверенные (≥ 0.8) *транзакционные* намерения; вопросы
  «как работает…», «в каком формате…» уходят в RAG (Mode B).
- **Полные ответы в отчёте**: сохранённый `benchmark_results.json` больше не
  обрезает ответы на 200 символах.
- **LLM-синтез всегда выполняется для Mode B**: адаптирует и проверяет
  извлечённый ответ под конкретный вопрос (с `max_tokens=32768`).
- **Воспроизводимые логи**: `benchmark.log` перезаписывается при каждом запуске,
  прогресс выводится как `QUESTION i/N`.

## Компоненты и сервисы

### Структура проекта

```
src/
├── core/              # Конфигурация и утилиты
├── domain/            # Бизнес-сущности и интерфейсы
├── infrastructure/    # БД, M2M клиенты, внешние сервисы
│   ├── db/
│   │   ├── session.py       # SQLAlchemy setup
│   │   └── models.py        # ORM модели
│   └── m2m/
│       ├── clients.py       # Real M2M API клиенты
│       ├── mock_clients.py  # Mock клиенты для dev
│       └── factory.py       # Выбор real vs mock
├── services/          # Бизнес-логика
│   ├── fsm.py               # FSM для Режима A
│   ├── llm.py               # LLM сервис (OpenAI, Anthropic)
│   ├── llm_investigation.py # RAG для Режима B
│   ├── handoff_engine.py    # Эскалация
│   ├── approval_service.py  # Управление одобрениями
│   └── identity.py          # Binding Telegram ID
├── presentation/      # API и Telegram обработчики
│   ├── telegram/
│   │   ├── handlers.py
│   │   ├── referral_flow.py
│   │   ├── review_flow.py
│   │   ├── refund_handlers.py
│   │   ├── jobs_handlers.py
│   │   ├── approval_handlers.py
│   │   └── mode_b_handlers.py
│   └── api/
│       └── routes.py
└── benchmarking/      # Система оценки качества
    ├── benchmark.py          # Основной бенчмарк скрипт
    ├── interactive_demo.py    # Интерактивная демонстрация
    ├── hybrid_retriever.py    # Гибридный поиск (BM25 + semantic)
    ├── flow_matcher.py        # Классификация потоков (Режим A)
    ├── intent_router.py       # Маршрутизация (MODE_A vs MODE_B)
    ├── llm_improver.py        # Улучшение LLM ответов
    ├── confidence_calculator.py  # Scoring уверенности
    └── faiss_cache.py         # Кэширование эмбеддингов
```

### Основные сервисы

| Сервис | Назначение | Статус |
|--------|-----------|--------|
| **ApprovalService** | Управление одобрениями с frozen параметрами | Production |
| **IdentityService** | Binding Telegram ID к QuickOffer аккаунту | Production |
| **InvestigationService** | RAG исследование + LLM синтез | Production |
| **HandoffService** | Детектирование 7 триггеров эскалации | Production |
| **OpenAILLMService** | LLM интеграция с OpenAI | Production |
| **AnthropicLLMService** | LLM интеграция с Anthropic | Production |
| **HybridRetriever** | Гибридный поиск (BM25 + semantic + rerank) | Production |

### 📊 Бенчмарк-скрипт (`src/benchmarking/benchmark.py`)


Запустите оценку производительности на 10 тестовых вопросах:

```bash
python -m src.benchmarking.benchmark
```

Выводит `benchmark_results.json` с:
- Точность матчинга потоков
- Качество RAG retrieval
- Эффективность улучшения LLM
- Распределение уверенности
- Этапы конвейера обработки

### 🎮 Интерактивная демонстрация (`src/benchmarking/interactive_demo.py`)

Протестируйте бота в интерактивном режиме:

```bash
python -m src.benchmarking.interactive_demo
```

Позволяет тестировать в реальном времени:
1. Матчинг потоков
2. RAG retrieval
3. Улучшение LLM
4. Оценку уверенности ответов

### ✅ Тестирование Mode B

```python
# tests/test_handoff_triggers.py
pytest tests/test_handoff_triggers.py -v

# Примеры тестов:
test_trigger_1_explicit_request_english()
test_trigger_2_identity_not_verified()
test_trigger_3_money_issue_refund()
test_trigger_4_account_security_hacked()
test_trigger_5_data_request_export()
test_trigger_6_tool_failure_cascade()
test_trigger_7_double_llm_failure()
test_no_trigger_normal_question()
```

### 🎯 Best Practices

#### ✅ DO:

- ✅ Регулярно обновляйте KB версии
- ✅ Четко определяйте owner и review_date
- ✅ Тестируйте каждый триггер handoff
- ✅ Логируйте все исследования
- ✅ Мониторьте confidence score
- ✅ Сохраняйте conversation history

#### ❌ DON'T:

- ❌ Не передавайте mutation tools в LLM
- ❌ Не используйте draft/archived KB
- ❌ Не игнорируйте handoff триггеры
- ❌ Не собирайте sensitive данные в KB
- ❌ Не устанавливайте confidence_threshold < 0.5
- ❌ Не удаляйте историю escalation

### 🚀 Deployment

#### 1. Применить миграции

```bash
alembic upgrade head
```

#### 2. Инициализировать KB версию

```python
from src.services.llm_investigation import InvestigationService
from datetime import datetime, timedelta

service = InvestigationService()

entries = [
    KnowledgeBaseEntry(
        entry_id="faq_1",
        category="General",
        title="How to reset password?",
        content="Visit account settings...",
        access_level="public",
    ),
    # ... more entries
]

service.register_kb_version(
    kb_id="faq_main",
    owner="support_team",
    version="1.0.0",
    effective_date=datetime.utcnow(),
    review_date=datetime.utcnow() + timedelta(days=90),
    entries=entries,
)
```

#### 3. Запустить бота

```bash
docker-compose up -d
```

### 📊 Мониторинг

Ключевые метрики для мониторинга:

```
handoff_tickets_created_total      # Общее количество escalation
handoff_triggers_by_type           # Распределение по типам
investigation_confidence_avg       # Средняя confidence
investigation_duration_seconds     # Время расследования
llm_failures_total                 # Ошибки LLM
tool_failures_total                # Ошибки инструментов
```

### 🔐 Security

- 🔒 KB версии хешируются (SHA256)
- 🔒 Handoff факты заморожены и неизменяемы
- 🔒 LLM не видит mutation tools
- 🔒 Все операции логируются в AuditLog
- 🔒 Sensitive данные маскированы в инструментах

### 📚 Дополнительные ресурсы

- `src/services/llm_investigation.py` - RAG-модуль (370 строк)
- `src/services/llm_tools.py` - Tools Registry (500 строк)
- `src/services/handoff_engine.py` - Handoff Engine (420 строк)
- `src/presentation/telegram/mode_b_handlers.py` - Telegram integration (250 строк)
- `tests/test_handoff_triggers.py` - Integration tests (300 строк)
- `migrations/versions/003_add_mode_b_tables.py` - DB migrations

### 📈 Статистика Mode B

| Компонент | Строк кода | Функции | Классы |
|-----------|-----------|---------|--------|
| llm_investigation.py | 370 | 12 | 5 |
| llm_tools.py | 500 | 25 | 9 |
| handoff_engine.py | 420 | 18 | 5 |
| mode_b_handlers.py | 250 | 3 | 1 |
| tests | 300 | 24 | 3 |
| **TOTAL** | **1840** | **82** | **23** |

### ✨ Резюме Mode B

✅ **Полная RAG-интеграция** - Knowledge Base versioning, классификация, retrieval
✅ **Read-Only Tools** - 8 инструментов, физически изолированы от мутаций
✅ **7 Handoff Триггеров** - Явный запрос, identity, money, security, data, tool failures, LLM failures
✅ **Automatic Escalation** - Создание тикета, уведомление админов с контекстом
✅ **Confidence Scoring** - Оценка надежности ответа
✅ **Fact Collection** - Сохранение собранных фактов для оператора
✅ **Full Audit Trail** - Полное логирование всех операций
✅ **Production Ready** - Протестировано, типизировано, задокументировано
