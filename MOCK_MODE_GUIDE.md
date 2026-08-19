# QuickOffer Support Bot - Mock Mode Guide

## 🎯 Обзор

Этот гайд описывает как запустить бота в **Mock Mode** для локального тестирования без доступа к реальным M2M API.

## ✨ Возможности Mock Mode

- ✅ **Полная функциональность FSM**: Все flows работают как в production
- ✅ **Mock M2M API**: Реалистичные mock-ответы от FuckHR и Jobs API
- ✅ **SQLite База данных**: Локальная БД для быстрого запуска
- ✅ **Telegram Polling**: Используется polling вместо webhooks
- ✅ **Feature Flag**: Легко переключаться между mock и real режимами

## 🚀 Быстрый Старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Проверка .env

Убедитесь, что в `.env` установлены следующие переменные:

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=<ваш_bot_token_от_BotFather>
TELEGRAM_APPROVAL_CHAT_ID=<чат_для_одобрения>

# Database Configuration (SQLite для локального тестирования)
DATABASE_URL=sqlite+aiosqlite:///./bot_local.db

# M2M API Configuration (будут проигнорированы в mock-режиме)
M2M_API_KEY=mock_m2m_key
FUCKHR_API_BASE_URL=http://localhost:8001
JOBS_API_BASE_URL=http://localhost:8002

# Mock Mode (ГЛАВНОЕ!)
USE_MOCKS=true

# LLM Configuration
LLM_PROVIDER_KEY=<ваш_llm_key>
LLM_PROVIDER=openai
LLM_MODEL=<модель>
LLM_BASE_URL=https://litellm.ai.nestle.ru/v1

# Application Configuration
LOG_LEVEL=DEBUG
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Инициализация БД (первый запуск)

```bash
# Создать БД и применить миграции
alembic upgrade head
```

### 4. Запуск бота

```bash
python run_bot.py
```

Вы увидите примерно следующий вывод:

```
============================================================
QuickOffer Support Bot - Demo Mode
============================================================
✅ Running in MOCK MODE (USE_MOCKS=true)
   - FuckHR API: Mock client
   - Jobs API: Mock client
   - Database: SQLite (local)
Bot Token: YOUR_TOKEN***
Approval Chat ID: -559415742
============================================================
Initializing database...
✅ Database initialized successfully
============================================================
🚀 Bot is ready!
Starting polling...
============================================================
```

## 🧪 Тестирование в Telegram

После запуска бота, откройте Telegram и напишите боту:

### Flow 1: Запрос возврата средств

```
/refund
```

Следуйте инструкциям:

- Выберите платеж для возврата
- Укажите причину возврата
- Добавьте доказательства (ссылки/описание)
- Подтвердите запрос

Mock система вернет успешный ответ и сохранит данные в БД.

### Flow 2: Архивирование вакансии

```
/archive_job
```

Следуйте инструкциям:

- Укажите ID или URL вакансии
- Выберите тип requester'а
- Укажите причину архивирования
- Добавьте доказательства
- Подтвердите запрос

## 📊 Структура Mock Данных

### MockFuckHRAPIClient

Возвращает mock-ответы для:

- `escalate` - Эскалация проблемы
- `reassign` - Переназначение сотруднику
- `resolve` - Разрешение проблемы
- `update_metadata` - Обновление метаданных

**Пример ответа:**

```json
{
  "status": "success",
  "action_id": "550e8400-e29b-41d4-a716-446655440000",
  "escalated_to": "senior_manager",
  "timestamp": "2026-08-19T15:06:00Z",
  "message": "Issue escalated to senior management"
}
```

### MockJobsAPIClient

Возвращает mock-ответы для:

- `create_job` - Создание новой вакансии
- `publish_job` - Публикация вакансии
- `close_job` - Закрытие вакансии
- `referral` - Создание реферального заявления

**Пример ответа:**

```json
{
  "status": "success",
  "action_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "title": "New Position",
  "department": "Engineering",
  "created_at": "2026-08-19T15:06:00Z",
  "message": "Job position created successfully"
}
```

## 🔄 Переключение между Mock и Real режимами

### Включить Mock Mode:

```env
USE_MOCKS=true
```

### Отключить Mock Mode (использовать реальные API):

```env
USE_MOCKS=false
```

**Важно**: Для работы с real API понадобятся:

- `M2M_API_KEY` - Валидный API ключ для M2M операций
- `FUCKHR_API_BASE_URL` - URL реального FuckHR API
- `JOBS_API_BASE_URL` - URL реального Jobs API

## 📁 Расположение файлов Mock

- `src/infrastructure/m2m/mock_clients.py` - Реализация mock-клиентов
- `src/infrastructure/m2m/factory.py` - Фабрика для выбора клиентов
- `src/core/config.py` - Конфигурация (включая флаг `use_mocks`)

## 🐛 Отладка

### Посмотреть логи

Логи выводятся в консоль с уровнем DEBUG:

```
DEBUG - [Bot is ready!]
DEBUG - [Poll timeout: 30 seconds]
```

### Проверить БД

SQLite БД находится в корне проекта:

```bash
sqlite3 bot_local.db
sqlite> .tables
sqlite> SELECT * FROM support_ticket;
```

### Очистить БД и начать заново

```bash
rm bot_local.db
python run_bot.py
```

## 🎓 Примеры использования Mock API

### Как Mock возвращает разные статусы

Mock система использует детерминистический подход для возврата статусов:

- Для одного и того же `action_id` всегда будет возвращен один и тот же статус
- Статусы цикличны: `pending` → `processing` → `completed` → `completed`

```python
# Пример из MockFuckHRAPIClient
statuses = ["pending", "processing", "completed", "completed"]
hash_value = hash(str(action_id)) % len(statuses)
return statuses[hash_value]
```

## 📝 Полезные команды

```bash
# Запустить бота
python run_bot.py

# Проверить синтаксис всех файлов
python -m py_compile src/infrastructure/m2m/mock_clients.py

# Запустить тесты (если есть)
pytest tests/

# Проверить типы с mypy
mypy src/

# Отформатировать код
black src/

# Сортировать импорты
isort src/
```

## ⚠️ Важные замечания

1. **Mock режим - только для разработки и тестирования**. Не используйте в production.
2. **SQLite - не рекомендуется для production**. Используйте PostgreSQL.
3. **Polling vs Webhooks**: В demo режиме используется polling (более медленно, но проще для локального запуска).
4. **Одобрение действий**: В mock режиме действия все равно отправляются в chat для одобрения (TELEGRAM_APPROVAL_CHAT_ID), но mock API сразу вернет успешный ответ.

## 🔗 Дополнительные ресурсы

- [aiogram v3 документация](https://docs.aiogram.dev/en/latest/)
- [FastAPI документация](https://fastapi.tiangolo.com/)
- [SQLAlchemy AsyncORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic v2](https://docs.pydantic.dev/latest/)

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте, что `USE_MOCKS=true` в `.env`
2. Проверьте логи в консоли (они очень детальные в DEBUG режиме)
3. Убедитесь, что TELEGRAM_BOT_TOKEN валиден
4. Очистите БД и начните заново: `rm bot_local.db && python run_bot.py`

---

**Готово к тестированию!** 🚀

Запустите `python run_bot.py` и начните тестировать flows в Telegram.
