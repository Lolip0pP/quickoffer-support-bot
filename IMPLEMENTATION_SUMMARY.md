# Mock Mode Implementation Summary

## 📋 Что было сделано

Реализован полноценный **Mock Mode** для локального тестирования QuickOffer Support Bot без доступа к реальным M2M API.

## ✨ Ключевые особенности

### 1. Feature Flag `USE_MOCKS`
- **Файл**: `src/core/config.py`
- **Переменная окружения**: `USE_MOCKS=true/false`
- Позволяет легко переключаться между mock и real режимами

### 2. Mock M2M Клиенты
- **Файл**: `src/infrastructure/m2m/mock_clients.py`
- **Компоненты**:
  - `MockFuckHRAPIClient` - Mock для FuckHR API
  - `MockJobsAPIClient` - Mock для Jobs API
- **Возвращаемые данные**: Реалистичные JSON-ответы, соответствующие API контрактам

### 3. M2M Фабрика
- **Файл**: `src/infrastructure/m2m/factory.py`
- **Функции**:
  - `get_fuckhr_client()` - Возвращает mock или real FuckHR клиент
  - `get_jobs_client()` - Возвращает mock или real Jobs клиент
- **Логика**: Выбор клиента основан на флаге `USE_MOCKS`

### 4. Обновленные хендлеры
Все места использования M2M клиентов обновлены для использования фабрики:
- `src/presentation/telegram/jobs_handlers.py` - Архивирование вакансий
- `src/presentation/telegram/refund_handlers.py` - Обработка возвратов

**Изменения**:
```python
# Было:
jobs_client = JobsAPIClient()

# Стало:
jobs_client = get_jobs_client()  # Автоматически выбирает mock или real
```

### 5. SQLite поддержка
- **.env**: Уже настроен для SQLite (`DATABASE_URL=sqlite+aiosqlite:///./bot_local.db`)
- **Преимущества**: Быстрый запуск, нет необходимости в PostgreSQL локально
- **Миграции**: Работают как с PostgreSQL, так и с SQLite

### 6. Run скрипт
- **Файл**: `run_bot.py`
- **Функционал**:
  - Инициализация БД
  - Логирование режима работы (mock/real)
  - Запуск Telegram polling
  - Красивый логический вывод

## 📁 Структура изменений

```
src/
├── core/
│   └── config.py                    # +USE_MOCKS флаг
├── infrastructure/
│   └── m2m/
│       ├── __init__.py              # +импорты mock клиентов и фабрики
│       ├── mock_clients.py           # НОВЫЙ файл
│       └── factory.py                # НОВЫЙ файл
└── presentation/
    └── telegram/
        ├── jobs_handlers.py          # Обновлены импорты и использование
        └── refund_handlers.py        # Обновлены импорты и использование

.env.example                          # +USE_MOCKS=false
.env                                  # USE_MOCKS=true (для демо)
run_bot.py                            # НОВЫЙ файл
MOCK_MODE_GUIDE.md                    # НОВЫЙ файл (подробный гайд)
IMPLEMENTATION_SUMMARY.md             # ЭТОТ файл
```

## 🚀 Как запустить

### Быстрый старт (2 минуты)

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Инициализировать БД (первый раз)
alembic upgrade head

# 3. Запустить бота
python run_bot.py
```

### В Telegram

```
/refund        - Запрос возврата средств
/archive_job   - Архивирование вакансии
```

## 🔧 Технические детали

### MockFuckHRAPIClient

**Поддерживаемые action_type**:
- `escalate` - Эскалация проблемы
- `reassign` - Переназначение сотруднику
- `resolve` - Разрешение проблемы
- `update_metadata` - Обновление метаданных

**Пример использования**:
```python
client = MockFuckHRAPIClient()
response = await client.execute_action(
    action_id=uuid.uuid4(),
    action_type="escalate",
    payload={"staff_id": "manager_123"},
    idempotency_key="idempotency_key_1"
)
# Вернет: {"status": "success", "escalated_to": "senior_manager", ...}
```

### MockJobsAPIClient

**Поддерживаемые action_type**:
- `create_job` - Создание вакансии
- `publish_job` - Публикация вакансии
- `close_job` - Закрытие вакансии
- `referral` - Создание реферала

**Пример использования**:
```python
client = MockJobsAPIClient()
response = await client.execute_action(
    action_id=uuid.uuid4(),
    action_type="referral",
    payload={"candidate_name": "John Doe", "position": "Engineer"},
    idempotency_key="idempotency_key_1"
)
# Вернет: {"status": "success", "referral_id": "...", ...}
```

### Детерминистичные статусы

Mock клиенты возвращают детерминистичные статусы на основе хеша `action_id`:
```python
statuses = ["pending", "processing", "completed", "completed"]
hash_value = hash(str(action_id)) % len(statuses)
return statuses[hash_value]
```

**Преимущества**:
- Один и тот же `action_id` всегда вернет один и тот же статус
- Позволяет тестировать идемпотентность
- Воспроизводимые тесты

## 🔄 Переключение режимов

### Включить Mock Mode
```env
USE_MOCKS=true
```

### Отключить (использовать real API)
```env
USE_MOCKS=false
M2M_API_KEY=real_api_key
FUCKHR_API_BASE_URL=https://api.fuckhr.com
JOBS_API_BASE_URL=https://api.jobs.com
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
```

## 📊 Примеры Mock Ответов

### FuckHR API - Escalate

```json
{
  "status": "success",
  "action_id": "550e8400-e29b-41d4-a716-446655440000",
  "escalated_to": "senior_manager",
  "timestamp": "2026-08-19T15:06:00Z",
  "message": "Issue escalated to senior management"
}
```

### Jobs API - Referral

```json
{
  "status": "success",
  "action_id": "550e8400-e29b-41d4-a716-446655440000",
  "referral_id": "550e8400-e29b-41d4-a716-446655440001",
  "candidate_name": "John Doe",
  "position": "Engineer",
  "referred_at": "2026-08-19T15:06:00Z",
  "message": "Referral created successfully"
}
```

## ✅ Проверка работоспособности

### Синтаксис

```bash
python -m py_compile \
  src/infrastructure/m2m/mock_clients.py \
  src/infrastructure/m2m/factory.py \
  src/presentation/telegram/jobs_handlers.py \
  src/presentation/telegram/refund_handlers.py
```

### Импорты

```bash
python -c "from src.infrastructure.m2m import get_fuckhr_client, get_jobs_client; print('OK')"
```

### БД Миграции

```bash
alembic upgrade head
```

## 🎯 Тестирование

### Unit тесты (примеры)

```python
import pytest
from src.infrastructure.m2m import get_fuckhr_client, get_jobs_client

@pytest.mark.asyncio
async def test_fuckhr_mock_escalate():
    client = get_fuckhr_client()
    response = await client.execute_action(
        action_id=uuid.uuid4(),
        action_type="escalate",
        payload={"staff_id": "manager_123"},
        idempotency_key="test_key"
    )
    assert response["status"] == "success"
    assert "escalated_to" in response
```

## 📈 Что дальше?

### Для production:

1. **PostgreSQL**: Замените `DATABASE_URL` на реальный PostgreSQL
2. **Real API**: Установите `USE_MOCKS=false` и используйте реальные credentials
3. **WebHooks**: Переключитесь с polling на webhooks для лучшей производительности
4. **Error Handling**: Добавьте более детальную обработку ошибок для real API

### Для разработки:

1. **Unit тесты**: Добавьте тесты для mock клиентов
2. **Integration тесты**: Тестируйте полные flows с mock режимом
3. **Load тесты**: Проверьте производительность с реальными нагрузками

## 🐛 Известные ограничения

1. **Mock режим не использует M2M_API_KEY** - В mock режиме ключ игнорируется
2. **SQLite не рекомендуется для production** - Используйте PostgreSQL
3. **Polling медленнее webhooks** - Для production используйте webhooks
4. **Mock не имитирует ошибки** - Все операции в mock режиме успешны

## 📚 Документация

- `MOCK_MODE_GUIDE.md` - Подробный гайд по запуску и тестированию
- `README.md` - Основная документация проекта
- `README_RU.md` - Документация на русском

## 🎉 Готово!

Mock режим полностью готов к использованию. Запустите `python run_bot.py` и начните тестировать!

---

**Автор**: Cline AI Assistant  
**Дата**: 2026-08-19  
**Статус**: ✅ Завершено
