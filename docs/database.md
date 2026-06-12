# База данных

Архитектура базы данных построена на PostgreSQL, SQLAlchemy и Alembic. Подключения задаются через переменные окружения `DATABASE_SYNC_URL` и `DATABASE_ASYNC_URL`.

## Стек

- PostgreSQL - основная СУБД.
- SQLAlchemy - ORM и описание моделей.
- Alembic - миграции и контроль версий схемы.
- `psycopg2` - синхронный драйвер для Alembic и sync-подключений.
- `asyncpg` - асинхронный драйвер для runtime async-подключений.

## Структура

- `database/config.py` - sync/async engine и session factories.
- `database/models/` - SQLAlchemy-модели.
- `database/alembic/` - конфигурация и версии миграций.
- `api/enums/enums_v1.py` - enum-значения для моделей.
- `api/config.py` - общие лимиты и ссылки для бизнес-логики.
- `api/payments/config.py` - платежные параметры, влияющие на `orders_payment_data`.

## Таблицы

### `users`

Пользователи системы: клиенты и исполнители.

Поля:

- `id`
- `first_name`
- `last_name`
- `phone_number`
- `ppd`
- `role`
- `created_at`
- `updated_at`

Особенности:

- `phone_number` уникален.
- `role` использует `UserRoles`.
- `id` связан с `orders.client_id`, `orders.performer_id`, `notifications.user_id` и `user_refresh_tokens.user_id`.

### `user_refresh_tokens`

Refresh token-ы пользователей.

Поля:

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `created_at`
- `updated_at`

Особенности:

- `user_id -> users.id` с `ON DELETE CASCADE`.
- `token_hash` уникален.
- таблица используется для refresh flow и logout.

### `orders`

Сделки между заказчиком и исполнителем.

Поля:

- `id`
- `client_id`
- `performer_id`
- `title`
- `conditions`
- `result_requirements`
- `violation_proof_requirements`
- `slug`
- `price`
- `status`
- `checked_by_worker_at`
- `expire_in`
- `created_at`
- `updated_at`
- `completed_at`

Особенности:

- `client_id` и `performer_id` ссылаются на `users.id`.
- `status` использует `OrderStates`, включая `awaiting_performer_payout`.
- `checked_by_worker_at` и `expire_in` используются воркером истечения сделок.
- `completed_at` заполняется при переходе в `awaiting_client_confirmation` и в закрытые статусы.
- `slug` уникален и используется для ссылок на экран сделки.

### `orders_payment_data`

Платежные данные сделки и состояние Paygine-операций.

Поля:

- `id`
- `order_id`
- `customer_email`
- `performer_email`
- `currency`
- `order_amount`
- `service_fee_amount`
- `payment_status`
- `payout_status`
- `revoke_status`
- `paygine_payment_operation_id`
- `paygine_payout_operation_id`
- `paygine_revoked_operation_id`
- `expire_payment_at`
- `expire_payout_at`
- `payout_completed_at`
- `payment_complete_at`
- `revoked_at`
- `created_at`
- `updated_at`

Особенности:

- `order_id -> orders.id` с `ON DELETE CASCADE`.
- `order_id` уникален, одна платежная запись на одну сделку.
- `paygine_payment_operation_id` и `paygine_payout_operation_id` уникальны.
- `payment_status`, `payout_status`, `revoke_status` используют `OrderPaymentStates`.
- `customer_email` заполняется при создании сделки.
- `performer_email` заполняется при принятии сделки исполнителем.
- `paygine_payment_operation_id` создается при регистрации депозитной сделки.
- `paygine_payout_operation_id` создается после подтверждения оплаты клиентом или при обработке просроченной сделки.
- `paygine_revoked_operation_id` используется для возвратных операций.
- `expire_payment_at` и `expire_payout_at` хранят дедлайны Paygine-операций.
- `payment_complete_at`, `payout_completed_at` и `revoked_at` фиксируют фактическое время завершения операций.

### `order_status_history`

История смены статусов сделки.

Поля:

- `id`
- `order_id`
- `old_status`
- `new_status`
- `changed_by_user_id`
- `created_at`

Особенности:

- `order_id -> orders.id`.
- `changed_by_user_id -> users.id`.
- таблица хранит основные переходы статусов, которые выполняются через API, воркер и payment webhook; payout-completed callback пишет только `orders` и `orders_payment_data`.

### `notifications`

Адресные уведомления пользователей.

Поля:

- `id`
- `user_id`
- `type`
- `status`
- `title`
- `text`
- `payload`
- `read_at`
- `created_at`
- `updated_at`

Особенности:

- `user_id -> users.id`.
- `type` использует `NotificationTypes`.
- `status` использует `NotificationStatuses`.

## Связи

- `orders.client_id -> users.id`
- `orders.performer_id -> users.id`
- `orders_payment_data.order_id -> orders.id`
- `order_status_history.order_id -> orders.id`
- `order_status_history.changed_by_user_id -> users.id`
- `notifications.user_id -> users.id`
- `user_refresh_tokens.user_id -> users.id`

## Enum-поля

Enum-поля хранятся как `VARCHAR + CHECK constraint`, без PostgreSQL native enum. Значения записываются в нижнем регистре через `.value` enum-классов.

Основные enum-наборы:

- `UserRoles`: `client`, `performer`
- `OrderStates`: статусы сделок, включая `awaiting_performer_payout`
- `OrderPaymentStates`: `registered`, `authorized`, `completed`, `blocked`, `canceled`, `expired`
- `NotificationTypes`: `order`, `review`, `promotion`, `news`
- `NotificationStatuses`: `unread`, `read`, `archived`, `failed`

## Миграции

Генерация миграции:

`alembic -c database/alembic/alembic.ini revision --autogenerate -m "base_revision"`

Применение миграций:

`alembic -c database/alembic/alembic.ini upgrade head`

Alembic использует синхронное подключение из `DATABASE_SYNC_URL`.

## Проверка enum

```sql
INSERT INTO users (id, first_name, last_name, phone_number, role)
VALUES (1, 'A', 'B', '+10000000001', 'CLIENT');

INSERT INTO users (id, first_name, last_name, phone_number, role)
VALUES (1, 'A', 'B', '+10000000001', 'client');
```

В первом случае ожидается ошибка проверки constraint, во втором - успешная вставка.
