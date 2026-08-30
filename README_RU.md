# QuickOffer Support Bot

Ядро обработки запросов поддержки: его можно запустить локально сейчас и подключить к Telegram позже.

- **Режим A** строит план одного из шести детерминированных сценариев. Изменяющие операции не доступны LLM и проходят через существующие approval/FSM.
- **Режим B** ищет ответ в базе знаний и при необходимости улучшает только read-only ответ с помощью LLM.
- Один `QuestionProcessor` используют локальная CLI, бенчмарки и будущие Telegram-обработчики.

## Локальный запуск

```bash
pip install -e '.[dev,benchmarking]'
python -m src.benchmarking.interactive_demo
pytest
```

Скопируйте `.env.example` в `.env` только для внешних сервисов. Демо работает без Telegram-учётных данных. См. [архитектуру](ARCHITECTURE.md) и [English README](README.md).
