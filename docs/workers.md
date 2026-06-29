# Воркеры

Воркеры запускаются отдельными процессами и выполняют фоновые задачи без HTTP-запросов. Подключение к базе выполняется через асинхронную SQLAlchemy-сессию из `database/config.py`.

## Стек

- Python asyncio - постоянный цикл фоновой обработки.
- SQLAlchemy async - асинхронные запросы к базе данных.
- PostgreSQL row locks - защита от одновременной обработки одной сделки несколькими воркерами.
- systemd - запуск и контроль процесса на сервере.

## Структура

- `workers/check_order_expire_time.py` - основной воркер проверки истекших сделок.
- `workers/utils/order_expire_methods.py` - логика выборки, проверки и обработки просроченных заказов.
- `api/payments/payments_methods.py` - платежные операции, которые вызывает воркер.
- `database/models/orders.py` - модель сделки и история статусов.
- `database/models/payments.py` - платежные поля и статусы Paygine.
- `api/enums/enums_v1.py` - статусы сделок и платежей.
- `api/config.py` - переменная `EXPIRE_TIME_TO_COMNFIRM_MINUTES`.
- `api/payments/config.py` - сроки истечения платежных и payout-операций.

## Запуск

Запуск воркера проверки истекших сделок:

`python -m workers.check_order_expire_time`

## Переменные окружения

Воркер использует те же переменные подключения к базе, что и API:

- `DATABASE_ASYNC_URL` - асинхронное подключение к PostgreSQL.
- `DATABASE_SYNC_URL` - синхронное подключение, используется Alembic и общим конфигом БД.
- `EXPIRE_TIME_TO_COMNFIRM_MINUTES` - время ожидания подтверждения заказчиком после завершения сделки исполнителем.

## Воркер истекших сделок

Файл:

`workers/check_order_expire_time.py`

Период проверки задается константой:

`WORKER_SLEEP_SECONDS = 60`

Размер батча задается константой:

`EXPIRED_ORDER_BATCH_SIZE = 1000`

Воркер обрабатывает только сделки в статусах:

- `awaiting_performer_confirmation`
- `awaiting_client_confirmation`

## Логика статусов

Сделки в статусе `awaiting_performer_confirmation` проверяются по полю `expire_in`.

Если `expire_in <= текущее время`, воркер:

- регистрирует возврат через `refund_money(...)` с `client_ref` заказчика;
- переводит сделку в `awaiting_client_payout`;
- сохраняет `paygine_revoked_operation_id` и `revoke_status = registered`.

Сделки в статусе `awaiting_client_confirmation` проверяются по полю `completed_at` и дельте `EXPIRE_TIME_TO_COMNFIRM_MINUTES`.

Если `completed_at <= текущее время - EXPIRE_TIME_TO_COMNFIRM_MINUTES`, воркер:

- регистрирует payout через `register_payout_deal(...)`;
- переводит сделку в `confirm_by_expire_time_to_performer`;
- устанавливает `orders_payment_data.payment_status = completed`;
- пишет `payment_complete_at`;
- сохраняет `paygine_payout_operation_id`;
- выставляет `payout_status = registered`;
- выставляет `expire_payout_at`.

При смене статуса воркер:

- обновляет `orders.status`;
- пишет запись в `order_status_history`.

## Совместная работа нескольких воркеров

Воркер учитывает параллельный запуск нескольких процессов.

Перед обработкой сделка атомарно помечается текущим временем в поле:

`orders.checked_by_worker_at`

В выборку попадают только сделки, у которых:

- `checked_by_worker_at IS NULL`;
- или `checked_by_worker_at <= текущее время - WORKER_SLEEP_SECONDS`.

Выборка использует блокировку:

`FOR UPDATE SKIP LOCKED`

Это позволяет нескольким воркерам работать одновременно: один процесс блокирует и помечает выбранные строки, остальные процессы пропускают заблокированные строки и не обрабатывают те же сделки повторно.

## Транзакции

Одна итерация воркера использует один `AsyncSession`.

Транзакции остаются короткими:

- отдельная транзакция для выбора и пометки батча сделок;
- отдельная транзакция для смены статуса каждой сделки.

## Логи

Воркер пишет результат каждой итерации в стандартный logging:

- количество отмененных сделок;
- количество подтвержденных сделок;
- ошибки итерации;
- пропущенные сделки, которые изменились между выборкой и обработкой.
