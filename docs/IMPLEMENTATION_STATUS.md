# Статус реализации по техническому заданию

## Реализовано в репозитории

- Telegram-адаптер, детерминированные флоу возврата, архивации вакансий,
  реферального и review-промокода.
- Изолированный read-only слой LLM, human handoff, модели действий, approvals,
  audit и M2M-клиенты с idempotency/trace заголовками.
- Fail-closed защита: бот не стартует без Telegram credentials; M2M-клиенты не
  делают запросов без ключа; callbacks требуют `X-Internal-Token`; CORS
  выключен, пока не задан явный allowlist.

## Внешние зависимости, которых нет в репозитории

Все такие места помечены единым комментарием `TODO(MAX)`.

1. Production Telegram bot/Business credentials, ID approval-чата и allowlist
   сотрудников.
2. Private ingress и контракт M2M (`mTLS` или short-lived service token) для
   основного API и `jobs-api`.
3. Production support DB, секрет-хранилище и миграционный контур.
4. Реальные YooKassa/foreign-card/crypto реквизиты, provider reconciliation и
   правила финансового учёта.
5. Curated knowledge base, LLM provider/model/retention/budget и monitoring.

До предоставления этих доступов заглушки **не имитируют успешную отправку в
Telegram**: handoff создаёт локальный идентификатор для текущего процесса, но
возвращает `notification_sent=false`. Это исключает ложное утверждение о
доставке обращения оператору.

## Перед развёртыванием

1. Скопировать `.env.example` в `.env` и заполнить все пустые секреты через
   secret manager.
2. Установить закрытые `CORS_ORIGINS` и уникальный
   `INTERNAL_WEBHOOK_TOKEN` в каждом окружении.
3. Заменить `TODO(MAX)` адаптеры на реальные и провести тесты replay/race,
   object-level authorization, cross-user disclosure и approval bypass из ТЗ.
