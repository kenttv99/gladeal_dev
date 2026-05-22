# База данных

Архитектура базы данных построена на PostgreSQL, SQLAlchemy и Alembic. Подключения к базе задаются через переменные окружения `DATABASE_SYNC_URL` и `DATABASE_ASYNC_URL`.

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

## Модели

- `users` - пользователи системы: клиенты и исполнители.
- `orders` - сделки, связанные с заказчиком и исполнителем.
- `order_status_history` - история смены статусов сделок.
- `notifications` - адресные уведомления пользователей.

Основные связи:

- `orders.client_id -> users.id`
- `orders.performer_id -> users.id`
- `order_status_history.order_id -> orders.id`
- `order_status_history.changed_by_user_id -> users.id`
- `notifications.user_id -> users.id`

## Миграции

Генерация миграции:
alembic -c database\alembic\alembic.ini revision --autogenerate -m "base_revision"


Применение миграций:
alembic -c database\alembic\alembic.ini upgrade head


Alembic использует синхронное подключение из `DATABASE_SYNC_URL`.

## Enum-поля

Enum-поля хранятся как `VARCHAR + CHECK constraint`, без PostgreSQL native enum. Значения записываются в нижнем регистре через `.value` enum-классов.

Основные enum-наборы:

- `UserRoles`: `client`, `performer`
- `OrderStates`: статусы сделок
- `NotificationTypes`: типы уведомлений
- `NotificationStatuses`: статусы уведомлений


Проверка корректной установки enum:
INSERT INTO users (id, first_name, last_name, phone_number, role) VALUES (1, 'A', 'B', '+10000000001', 'CLIENT'); - ожидается "ОШИБКА:  новая строка в отношении "users" нарушает ограничение-проверку"

INSERT INTO users (id, first_name, last_name, phone_number, role) VALUES (1, 'A', 'B', '+10000000001', 'client'); - ожидается УСПЕХ.