# FastAPI

API построен на FastAPI, асинхронных SQLAlchemy-сессиях и JWT-авторизации. Основная точка входа приложения - `api/servers/main.py`. Платежный callback-сервер вынесен в `api/servers/payments.py`.

## Стек

- FastAPI - HTTP API и Swagger-документация.
- Uvicorn - ASGI-сервер.
- SQLAlchemy async - асинхронная работа с базой данных в runtime.
- PyJWT - генерация и проверка access token.
- `secrets` + SHA-256 - генерация refresh token и хранение его hash в БД.
- Pydantic - request/response-схемы.

## Структура

- `api/servers/main.py` - создание основного приложения, CORS, exception handlers и подключение роутеров.
- `api/servers/payments.py` - отдельное приложение для Paygine webhook-ов и redirect-ов.
- `api/endpoints/v1/` - FastAPI-роутеры версии v1.
- `api/webhooks/v1/` - webhook-обработчики Paygine.
- `api/payments/` - сервисный слой интеграции с Paygine.
- `api/schemas/schemas_v1.py` - request/response-схемы.
- `api/utils/users_methods.py` - бизнес-методы пользователей.
- `api/utils/orders_methods.py` - бизнес-методы сделок.
- `api/utils/help_orders_method.py` - вспомогательные методы сделок.
- `api/utils/jwt_methods.py` - генерация access token, refresh token и проверка авторизации.
- `api/exceptions/` - локализованные JSON-ошибки.
- `api/config.py` - обязательные переменные окружения основного API.

## Запуск

Основной API:

`python -m api.servers.main`

Платежный callback-сервер:

`python -m api.servers.payments`

Swagger основного API:

`http://127.0.0.1:8000/docs`

OpenAPI JSON основного API:

`http://127.0.0.1:8000/openapi.json`

Платежный сервер поднимается на порту `8001` и обслуживает Paygine callback- и redirect-пути.

## Переменные окружения

Обязательные переменные основного API:

- `JWT_SECRET_KEY` - секрет для подписи JWT.
- `JWT_ALGORITHM` - алгоритм JWT, например `HS256`.
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - время жизни access token в минутах.
- `JWT_REFRESH_TOKEN_EXPIRE_MINUTES` - время жизни refresh token в минутах.
- `MONTH_SUM_LIMIT_PER_USER` - месячный лимит суммы сделок пользователя.
- `BASE_SITE_LINK` - базовый адрес сайта для формирования ссылок на сделки и Paygine notify URL.
- `EXPIRE_TIME_TO_COMNFIRM_MINUTES` - время ожидания подтверждения сделки в минутах.

Платежный контур использует отдельный `.env.payments`; подробный список переменных вынесен в [docs/payments.md](payments.md).

`BASE_SITE_LINK` используется для ссылок формата:

`{BASE_SITE_LINK}/active_deal/{slug}`

## Роутеры

- `/api/v1/auth` - регистрация, авторизация и управление аккаунтом.
- `/api/v1/client` - действия пользователя как заказчика.
- `/api/v1/performer` - действия пользователя как исполнителя.
- `/v1/paygine` - webhook-и и redirect-ы Paygine в отдельном приложении.

Роутеры клиента и исполнителя подключены с обязательной авторизацией. В auth-роутере публичными остаются регистрация, логин, обновление access token по refresh token и logout по refresh token.

## Авторизация

Авторизация реализована через `HTTPBasic` для корректного отображения в Swagger одним блоком авторизации.

В Swagger нужно указать:

- `username` - `user_id`
- `password` - `access_token`

Access token создается методом `generate_access_token(user_id)` и содержит:

- `sub`
- `user_id`
- `iat`
- `exp`

При каждом защищенном запросе проверяется, что `user_id` из авторизации совпадает с `user_id`, записанным в JWT. Для endpoint-методов, принимающих `user_id` в теле запроса, дополнительно вызывается `ensure_authorized_user_id`.

Запрос от имени другого пользователя блокируется ошибкой `ACCESS_DENIED`.

Refresh token является opaque-строкой. Backend возвращает raw refresh token клиенту. В БД хранит только SHA-256 hash в таблице `user_refresh_tokens`.

Таблица `user_refresh_tokens` содержит:

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `created_at`
- `updated_at`

Refresh token привязан к `user_id`. При удалении пользователя связанные refresh token записи удаляются каскадно.

Срок действия refresh token задается через `JWT_REFRESH_TOKEN_EXPIRE_MINUTES`. Refresh token используется для получения нового access token и не перезаписывается при обновлении access token.

## Auth endpoints

- `POST /api/v1/auth/register` - регистрация пользователя.
- `POST /api/v1/auth/login` - авторизация по номеру телефона и выдача access token + refresh token.
- `POST /api/v1/auth/access_token_refresh/` - обновление access token по refresh token.
- `POST /api/v1/auth/logout/` - отзыв refresh token.
- `POST /api/v1/auth/delete-account` - удаление аккаунта авторизованного пользователя.
- `POST /api/v1/auth/reset-phone-number` - смена номера телефона авторизованного пользователя.

Регистрация сохраняет:

- `first_name`
- `last_name`
- `phone_number`
- `ppd`

Номер телефона уникален на уровне БД. При срабатывании unique-ограничения возвращается локализованная JSON-ошибка `PHONE_NUMBER_ALREADY_EXISTS`.

Логин принимает:

- `phone_number`

Логин возвращает:

- `access_token`
- `refresh_token`
- `refresh_token_expires_at`
- `token_type`

Пример ответа login:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "refresh_token_expires_at": "2026-06-29T12:00:00+00:00",
  "token_type": "bearer"
}
```

`POST /api/v1/auth/access_token_refresh/` принимает:

- `refresh_token`

Endpoint проверяет наличие refresh token hash в БД и срок действия. Если refresh token валиден, backend выпускает новый access token и возвращает:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

`POST /api/v1/auth/logout/` принимает:

- `refresh_token`

Endpoint удаляет запись refresh token из `user_refresh_tokens` и возвращает:

```json
{"success": true}
```

Удаление аккаунта запрещено, если у пользователя есть активные сделки в статусах:

- `awaiting_performer`
- `awaiting_payment`
- `awaiting_performer_confirmation`
- `awaiting_client_confirmation`
- `awaiting_performer_payout`
- `awaiting_conflict`
- `open_conflict`

При блокировке удаления возвращается `ACCOUNT_DELETION_BLOCKED_BY_ACTIVE_ORDERS`.

Смена номера телефона проверяет, что новый номер не используется другим пользователем. При конфликте возвращается `PHONE_NUMBER_ALREADY_EXISTS`.

## Client endpoints

- `GET /api/v1/client/order_link` - возвращает ссылку на экран сделки по `order_id`.
- `GET /api/v1/client/order_info_by_slug` - возвращает информацию о сделке по `slug`.
- `GET /api/v1/client/order_info` - возвращает информацию о сделке по `order_id`.
- `GET /api/v1/client/deals` - возвращает активные сделки заказчика.
- `POST /api/v1/client/deal_create` - создает сделку и регистрирует депозитную операцию в Paygine.
- `POST /api/v1/client/deal_confirm` - завершает payment flow и запускает payout flow.
- `POST /api/v1/client/deal_softdecline` - завершает сделку как `unsuccessful_completion`, если исполнитель еще не назначен.
- `POST /api/v1/client/deal_harddecline` - переводит сделку в `awaiting_conflict`.
- `GET /api/v1/client/deal_payment_link` - возвращает signed Paygine URL для оплаты сделки.
- `GET /api/v1/client/deals_archive` - возвращает закрытые сделки заказчика.

Создание сделки:

- проверяет существование пользователя;
- проверяет месячный лимит суммы сделок через `MONTH_SUM_LIMIT_PER_USER`;
- генерирует уникальный `slug`;
- создает сделку в статусе `awaiting_performer`;
- записывает первое состояние в `order_status_history`;
- регистрирует депозитную сделку в Paygine;
- сохраняет платежные данные в `orders_payment_data`.

Если месячный лимит превышен, возвращается `MONTH_ORDERS_LIMIT_EXCEEDED` с деталями:

- `is_limit_exceeded`
- `delta`

Платежные эффекты клиентских endpoint-ов:

- `deal_payment_link` использует `paygine_payment_operation_id` и строит ссылку на `SDPayInDebit`.
- `deal_confirm` вызывает `SDComplete`, затем регистрирует payout-операцию для исполнителя и переводит сделку в `awaiting_performer_payout`.
- `deal_softdecline` вызывает `ChangeOrderStatus` с `EXPIRED`, если исполнитель еще не принял сделку.
- `deal_harddecline` не затрагивает Paygine и переводит сделку в конфликт.

## Performer endpoints

- `GET /api/v1/performer/deals` - возвращает активные сделки исполнителя.
- `POST /api/v1/performer/deal_approve` - назначает исполнителя и переводит сделку в `awaiting_payment`.
- `POST /api/v1/performer/deal_confirm` - переводит сделку в `awaiting_client_confirmation`.
- `POST /api/v1/performer/deal_decline` - завершает сделку как `unsuccessful_completion`.
- `POST /api/v1/performer/deal_conflict` - переводит сделку в `open_conflict`.
- `GET /api/v1/performer/deal_payout_link` - возвращает signed Paygine URL для получения средств.
- `GET /api/v1/client/deal_refund_link` - возвращает signed Paygine URL для получения возврата заказчиком.
- `GET /api/v1/performer/deals_archive` - возвращает закрытые сделки исполнителя.

Исполнитель не может принять или выполнять действия по собственной сделке. Если `client_id` сделки совпадает с `user_id` исполнителя, возвращается `ORDER_SELF_EXECUTION_FORBIDDEN`.

Принять можно только сделку в статусе `awaiting_performer` и без назначенного исполнителя. Если сделка уже принята или находится в неподходящем статусе, возвращается `ORDER_ALREADY_ACCEPTED`.

Платежные эффекты исполнительских endpoint-ов:

- `deal_approve` сохраняет `performer_email` в `orders_payment_data` и переводит сделку в `awaiting_payment`.
- `deal_decline` регистрирует возврат заказчику без сервисной комиссии и сохраняет `paygine_revoked_operation_id`.
- `deal_payout_link` использует `paygine_payout_operation_id` и строит ссылку на `SDPayOutPage`.
- `deal_refund_link` использует `paygine_revoked_operation_id` и строит ссылку на `SDPayOutPage`.

## Платежный контур

Подробная реализация платежных запросов и webhook-ов описана в:

- [payments.md](payments.md)
- [webhooks.md](webhooks.md)

Ключевые внешние события:

- `POST /api/v1/client/deal_create` - регистрация депозитной сделки.
- `POST /api/v1/client/deal_confirm` - завершение платежа и регистрация payout.
- `GET /api/v1/admin/close_to_client` - закрытие спора в пользу заказчика и регистрация возврата.
- `GET /api/v1/admin/close_to_performer` - закрытие спора в пользу исполнителя и регистрация payout.
- `POST /v1/paygine/webhook_order_status` - синхронизация статусов операций Paygine с БД.

## Статусы сделок

Активные статусы:

- `awaiting_performer`
- `awaiting_payment`
- `awaiting_performer_confirmation`
- `awaiting_client_confirmation`
- `awaiting_performer_payout`
- `awaiting_conflict`
- `open_conflict`

Закрытые статусы:

- `successful_completion`
- `unsuccessful_completion`
- `cancled_by_expire_time_to_client`
- `confirm_by_expire_time_to_performer`
- `closed_by_arbiter_to_client`
- `closed_by_arbiter_to_performer`

При установке любого закрытого статуса автоматически заполняется `completed_at`.

## История статусов

Основные смены статуса сделки записываются в `order_status_history`:

- `order_id`
- `old_status`
- `new_status`
- `changed_by_user_id`

Enum-значения сохраняются в БД через `.value`, в нижнем регистре.

Отдельные платежные обновления, которые не меняют `orders.status`, в историю не попадают. Payout-completed callback пишет строку в `order_status_history` и не перезаписывает expire-исходы на `successful_completion`.

## Ответы

Успешные мутационные endpoints возвращают JSON:

`{"success": true}`

Ссылка на сделку возвращается в формате:

`{"link": "https://gladeal.ru/active_deal/{slug}"}`

Ошибки возвращаются через единую локализованную систему:

- `error`
- `message`
- `details`

Язык ответа выбирается через заголовок `Accept-Language`.
