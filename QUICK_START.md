# 🚀 Quick Start - QuickOffer Support Bot (Mock Mode)

## 30 секунд до запуска бота

### 1️⃣ Установить зависимости
```bash
pip install -r requirements.txt
```

### 2️⃣ Инициализировать БД (первый раз)
```bash
alembic upgrade head
```

### 3️⃣ Запустить бота
```bash
python run_bot.py
```

## 📱 Тестировать в Telegram

После запуска напишите боту одну из команд:

```
/refund        👈 Запросить возврат денег
/archive_job   👈 Архивировать вакансию
/start         👈 Начать
/help          👈 Справка
```

## ✅ Проверка что всё работает

Вы должны увидеть логи:

```
============================================================
QuickOffer Support Bot - Demo Mode
============================================================
✅ Running in MOCK MODE (USE_MOCKS=true)
   - FuckHR API: Mock client
   - Jobs API: Mock client
   - Database: SQLite (local)
============================================================
✅ Database initialized successfully
============================================================
🚀 Bot is ready!
Starting polling...
============================================================
```

## 🔧 Важные параметры в .env

```env
# ГЛАВНОЕ - включен Mock Mode
USE_MOCKS=true

# Telegram Bot Token (от BotFather)
TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE

# Чат для одобрения действий
TELEGRAM_APPROVAL_CHAT_ID=-559415742

# База данных (SQLite для локального тестирования)
DATABASE_URL=sqlite+aiosqlite:///./bot_local.db
```

## 📚 Подробные гайды

- **`MOCK_MODE_GUIDE.md`** - Полный гайд с примерами
- **`IMPLEMENTATION_SUMMARY.md`** - Что было реализовано

## 🎯 Примеры использования

### Flow 1: Возврат денег
1. `/refund` - Начать
2. Выбрать платеж из списка (1-5)
3. Выбрать причину (1-4)
4. Добавить доказательства (ссылки/описание)
5. `confirm` - Подтвердить

### Flow 2: Архивирование вакансии
1. `/archive_job` - Начать
2. Ввести ID или URL вакансии
3. Выбрать тип requester'а (1-3)
4. Выбрать причину архивирования (1-7)
5. Добавить доказательства
6. `proceed` - Подтвердить

## 🐛 Если что-то не работает

```bash
# Очистить БД и начать заново
rm bot_local.db
python run_bot.py

# Или проверить импорты
python -c "from src.infrastructure.m2m import get_fuckhr_client; print('OK')"
```

## 💡 Ключевые особенности Mock Mode

✅ Полная функциональность как в production  
✅ Реалистичные mock-ответы от API  
✅ Местная SQLite БД (без PostgreSQL)  
✅ Telegram Polling (готов к боевым условиям)  
✅ Легко переключить на real режим (USE_MOCKS=false)  

## 🎓 Переключение на production режим

Когда получите доступ к реальным API:

```env
USE_MOCKS=false
M2M_API_KEY=your_real_key
FUCKHR_API_BASE_URL=https://api.fuckhr.com
JOBS_API_BASE_URL=https://api.jobs.com
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
```

Всё остальное будет работать как есть! 🎉

---

**Готово!** Запустите `python run_bot.py` и начните тестировать. 🚀
