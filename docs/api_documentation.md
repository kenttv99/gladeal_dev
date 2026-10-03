# FastAPI

API построен на FastAPI, асинхронных SQLAlchemy-сессиях и JWT-авторизации. Основная точка входа приложения - `api/servers/main.py`. Платежный callback-сервер вынесен в `api/servers/payments.py`.

## Стек

- FastAPI - HTTP API и Swagger-документация.
- Uvicorn - ASGI-сервер.
- SQLAlchemy async - асинхронная работа с базой данных в runtime.
- PyJWT - генерация и проверка access token.
- `secrets` + SHA-256 - генерация refresh token и хранение его hash в БД.
- Redis - хранение SMS/call кодов подтверждения и одноразовых verification-флагов.
- ProstoSMS - отправка кодов подтверждения через SMS и звонок.
- Pydantic - request/response-схемы.

## Структура

- `api/servers/main.py` - создание основного приложения, CORS, exception handlers и подключение роутеров.
- `api/servers/payments.py` - отдельное приложение для Paygine webhook-ов и redirect-ов.
- `api/endpoints/v1/` - FastAPI-роутеры версии v1.
- `api/webhooks/v1/` - webhook-обработчики Paygine.
- `api/payments/` - сервисный слой интеграции с Paygine.
- `api/sms_calls/` - сервисный слой интеграции с ProstoSMS и Redis-хранилище кодов.
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
- `BASE_SITE_LINK` - базовый адрес сайта для формирования ссылок на сделки и Paygine notify URL.
- `EXPIRE_TIME_TO_COMNFIRM_MINUTES` - время ожидания подтверждения сделки в минутах.
- `MAX_SINGLE_ORDER_PRICE` - максимальная сумма одной сделки (по умолчанию 100 000).
- `VERIFICATION_REQUIRED_PRICE_THRESHOLD` - порог суммы сделки, начиная с которого требуется верификация (по умолчанию 15 000).
- `PAYMENT_HOLD_DURATION_MINUTES` - длительность периода заморозки (холдирования) средств в минутах перед окончательным списанием (по умолчанию 5).

Платежный контур использует отдельный `.env.payments`; подробный список переменных вынесен в [docs/payments.md](payments.md).

Контур SMS/звонков использует отдельный `.env.sms_calls`:

- `PROSTO_SMS_BASE_URL` - базовый URL ProstoSMS API.
- `PROSTO_SMS_API_KEY` - API-ключ ProstoSMS.
- `SMS_CALLS_REDIS_URL` - Redis URL для хранения кодов и verification-флагов.
- `SMS_CALLS_CODE_TTL_SECONDS` - срок жизни кода и verification-флага в секундах.
- `SMS_CALLS_SEND_ATTEMPTS_LIMIT` - максимальное число отправок кода на цель и scope.
- `SMS_CALLS_SEND_LIMIT_PAUSE_MINUTES` - пауза в минутах после превышения лимита отправок.
- `SMS_CALLS_VERIFY_ATTEMPTS_LIMIT` - максимальное число неверных вводов текущего кода.

`BASE_SITE_LINK` используется для ссылок формата:

`{BASE_SITE_LINK}/active_deal/{slug}`

## Роутеры

- `/api/v1/auth` - регистрация, авторизация и управление аккаунтом.
- `/api/v1/users` - профиль и KYC верификация пользователя.
- `/api/v1/client` - действия пользователя как заказчика.
- `/api/v1/performer` - действия пользователя как исполнителя.
- `/api/v1/admin` - панель управления и действия администратора.
- `/v1/paygine` - webhook-и и redirect-ы Paygine в отдельном приложении.

Роутеры клиента и исполнителя подключены с обязательной авторизацией. В auth-роутере публичными остаются отправка и проверка кода, регистрация, логин и обновление access token по refresh token. `logout`, удаление аккаунта и смена номера телефона требуют access token.

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

- `POST /api/v1/auth/verification-code` - отправка кода подтверждения через SMS или звонок.
- `POST /api/v1/auth/verification-code/verify` - проверка кода подтверждения.
- `POST /api/v1/auth/register` - регистрация пользователя.
- `POST /api/v1/auth/login` - авторизация по номеру телефона и выдача access token + refresh token (или pre_auth_token при включенном 2FA).
- `POST /api/v1/auth/2fa/setup` - генерация секрета, QR-кода и резервных кодов для настройки 2FA.
- `POST /api/v1/auth/2fa/enable` - активация 2FA по 6-значному TOTP коду.
- `POST /api/v1/auth/2fa/verify` - завершение авторизации при включенном 2FA по pre_auth_token и TOTP/backup коду.
- `POST /api/v1/auth/2fa/disable` - отключение 2FA.
- `GET /api/v1/auth/2fa/status` - получение статуса 2FA и количества оставшихся резервных кодов.
- `POST /api/v1/auth/access_token_refresh/` - обновление access token по refresh token.
- `POST /api/v1/auth/logout/` - отзыв refresh token авторизованного пользователя.
- `POST /api/v1/auth/delete-account` - удаление аккаунта авторизованного пользователя.
- `POST /api/v1/auth/reset-phone-number` - смена номера телефона авторизованного пользователя.

### Коды подтверждения

`POST /api/v1/auth/verification-code` публичный и принимает:

- `phone_number`
- `verification_scope`: `register`, `login` или `reset_phone_number`
- `verification_method`: `sms` или `call`

Пример запроса:

```json
{
  "phone_number": "79000000001",
  "verification_scope": "register",
  "verification_method": "sms"
}
```

Endpoint проверяет лимит отправок, генерирует 4-значный код, сохраняет его в Redis с TTL `SMS_CALLS_CODE_TTL_SECONDS` и отправляет через ProstoSMS. Для `sms` используется текст `Код подтверждения: {code}`. Для звонка используется тот же payload с `route=pc`.

`POST /api/v1/auth/verification-code/verify` публичный и принимает:

- `phone_number`
- `verification_scope`: `register`, `login` или `reset_phone_number`
- `verification_code`

Пример запроса:

```json
{
  "phone_number": "79000000001",
  "verification_scope": "login",
  "verification_code": "1234"
}
```

Если код верный, backend атомарно удаляет Redis-ключ кода и создает одноразовый verification-флаг с тем же TTL. Основной endpoint затем потребляет этот флаг и удаляет его.

Если код неверный, backend увеличивает счетчик неверных вводов. При достижении `SMS_CALLS_VERIFY_ATTEMPTS_LIMIT` текущий код и счетчик удаляются, повторный перебор этого кода невозможен. При превышении `SMS_CALLS_SEND_ATTEMPTS_LIMIT` отправка блокируется на `SMS_CALLS_SEND_LIMIT_PAUSE_MINUTES` и возвращает `SMS_CALLS_RATE_LIMIT`.

Redis-ключи разделены по сценарию:

- `sms_calls:verification_code:register:phone:{phone}`
- `sms_calls:verification_attempts:register:phone:{phone}`
- `sms_calls:send_attempts:register:phone:{phone}`
- `sms_calls:verified:register:phone:{phone}`
- `sms_calls:verification_code:login:user:{user_id}`
- `sms_calls:verification_attempts:login:user:{user_id}`
- `sms_calls:send_attempts:login:user:{user_id}`
- `sms_calls:verified:login:user:{user_id}`
- `sms_calls:verification_code:reset_phone_number:phone:{phone}`
- `sms_calls:verification_attempts:reset_phone_number:phone:{phone}`
- `sms_calls:send_attempts:reset_phone_number:phone:{phone}`
- `sms_calls:verified:reset_phone_number:phone:{phone}`

Для `verification_scope=register` номер должен быть свободен. Для `verification_scope=login` пользователь с номером должен существовать. Для `verification_scope=reset_phone_number` номер должен быть свободен; сам основной endpoint смены номера дополнительно требует авторизацию.

Пример успешного ответа проверки:

```json
{"success": true}
```

Если код неверный, истек или verification-флаг уже был использован:

```json
{"success": false}
```

### Регистрация

Перед `POST /api/v1/auth/register` клиент должен вызвать:

1. `POST /api/v1/auth/verification-code` с `verification_scope=register`.
2. `POST /api/v1/auth/verification-code/verify` с `verification_scope=register`.

Регистрация сохраняет:

- `phone_number` (обязательно)
- `first_name` (опционально)
- `patronymic` (опционально)
- `last_name` (опционально)
- `birth_date` (опционально)
- `persondoc_number` (опционально)
- `ppd`

`POST /api/v1/auth/register` принимает `RegisterUserRequest` (для сделок до 15 000 ₽ достаточно передать только `phone_number`):

```json
{
  "first_name": "Иван",
  "patronymic": "Иванович",
  "last_name": "Иванов",
  "phone_number": "79000000001",
  "birth_date": "2000-01-15T00:00:00Z",
  "persondoc_number": "1234567890",
  "ppd": true
}
```

Endpoint потребляет одноразовый Redis-флаг `sms_calls:verified:register:phone:{phone}`. Если флага нет, возвращает:

```json
{"success": false}
```

Номер телефона уникален на уровне БД. При срабатывании unique-ограничения возвращается локализованная JSON-ошибка `PHONE_NUMBER_ALREADY_EXISTS`.

### Логин

Перед `POST /api/v1/auth/login` клиент должен вызвать:

1. `POST /api/v1/auth/verification-code` с `verification_scope=login`.
2. `POST /api/v1/auth/verification-code/verify` с `verification_scope=login`.

Логин принимает:

- `phone_number`

Логин возвращает:

- При отключенном 2FA (`is_two_factor_enabled == false`):
  - `access_token`
  - `refresh_token`
  - `refresh_token_expires_at`
  - `token_type`
- При включенном 2FA (`is_two_factor_enabled == true`):
  - `two_factor_required: true`
  - `pre_auth_token: "..."` (JWT со scope `2fa_pre_auth`, срок действия 5 минут)
  - `token_type: "pre_auth"`

Endpoint потребляет одноразовый Redis-флаг `sms_calls:verified:login:user:{user_id}`. Если флага нет, возвращает:

```json
{"success": false}
```

Пример ответа login без 2FA:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "refresh_token_expires_at": "2026-06-29T12:00:00+00:00",
  "token_type": "bearer"
}
```

Пример ответа login с 2FA:

```json
{
  "two_factor_required": true,
  "pre_auth_token": "...",
  "token_type": "pre_auth"
}
```

### Двухфакторная аутентификация (2FA / TOTP)

Двухфакторная аутентификация построена на стандарте TOTP (RFC 6238 / RFC 4226) и совместима с Google Authenticator, Microsoft Authenticator и другими приложениями.

#### Настройка 2FA (`POST /api/v1/auth/2fa/setup`):
- Требует авторизации (`Bearer access_token`).
- Генерирует секретный ключ Base32, URL формата `otpauth://totp/...`, Base64 PNG изображение QR-кода и 8 одноразовых резервных кодов (например, `A1B2-C3D4`).
- Секрет и хэши резервных кодов сохраняются в профиле, флаг `is_two_factor_enabled` остается `false` до подтверждения.
- Пример ответа:
```json
{
  "secret": "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
  "otpauth_url": "otpauth://totp/Gladeal:+79000000001?secret=...",
  "qr_code_base64": "data:image/png;base64,...",
  "backup_codes": ["A1B2-C3D4", "E5F6-G7H8", "I9J0-K1L2", "M3N4-O5P6", "Q7R8-S9T0", "U1V2-W3X4", "Y5Z6-A7B8", "C9D0-E1F2"]
}
```

#### Активация 2FA (`POST /api/v1/auth/2fa/enable`):
- Принимает:
```json
{
  "code": "123456"
}
```
- Проверяет 6-значный TOTP код, защищает от Replay-атаки через Redis (окно 90 секунд) и переводит `is_two_factor_enabled` в `true`.

#### Завершение входа по второму фактору (`POST /api/v1/auth/2fa/verify`):
- Публичный эндпоинт, принимает:
```json
{
  "pre_auth_token": "...",
  "code": "123456"
}
```
- В поле `code` передается 6-значный код из Google Authenticator или один из неиспользованных резервных кодов (`A1B2-C3D4`).
- При вводе резервного кода соответствующий хэш сжигается (удаляется из БД).
- При успехе выпускаются боевые `access_token` и `refresh_token`.

#### Отключение 2FA (`POST /api/v1/auth/2fa/disable`):
- Принимает `code` (текущий TOTP код или резервный код) и сбрасывает настройки 2FA.

#### Статус 2FA (`GET /api/v1/auth/2fa/status`):
- Возвращает `{ "is_two_factor_enabled": true, "backup_codes_remaining": 7 }`.

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

Endpoint требует access token в HTTPBasic-авторизации. Он удаляет запись refresh token из `user_refresh_tokens` только если token принадлежит авторизованному `user_id`, и возвращает:

```json
{"success": true}
```

Удаление аккаунта запрещено, если у пользователя есть активные сделки в статусах:

- `awaiting_performer`
- `awaiting_payment`
- `awaiting_performer_confirmation`
- `awaiting_client_confirmation`
- `awaiting_performer_payout`
- `awaiting_client_payout`
- `awaiting_conflict`
- `open_conflict`

При блокировке удаления возвращается `ACCOUNT_DELETION_BLOCKED_BY_ACTIVE_ORDERS`.

Смена номера телефона проверяет, что новый номер не используется другим пользователем. При конфликте возвращается `PHONE_NUMBER_ALREADY_EXISTS`.

Перед `POST /api/v1/auth/reset-phone-number` клиент должен вызвать:

1. `POST /api/v1/auth/verification-code` с `verification_scope=reset_phone_number`.
2. `POST /api/v1/auth/verification-code/verify` с `verification_scope=reset_phone_number`.

Оба verification endpoint для этого scope вызываются без авторизации. Основной `POST /api/v1/auth/reset-phone-number` требует access token, повторно проверяет доступность номера и потребляет одноразовый Redis-флаг `sms_calls:verified:reset_phone_number:phone:{phone}`.

## KYC endpoints (Идентификация пользователя)

- `POST /api/v1/auth/kyc/verify` - запускает идентификацию пользователя в Paygine по его паспортным данным (`persondoc_number`, `birth_date`, `first_name`, `last_name`, `patronymic`). Принимает опциональное тело `UserKYCVerifyRequest` для дозаполнения или обновления персональных данных перед проверкой.
- `GET /api/v1/auth/kyc/status` - возвращает сохраненный статус верификации пользователя.

Оба эндпоинта требуют авторизации (`Bearer access_token`).
Тело `POST /api/v1/auth/kyc/verify` (`UserKYCVerifyRequest`):
```json
{
  "first_name": "Иван",
  "patronymic": "Иванович",
  "last_name": "Иванов",
  "birth_date": "2000-01-15T00:00:00Z",
  "persondoc_number": "1234 567890"
}
```
Если у пользователя в БД и в теле запроса не заполнены ФИО (`first_name`, `patronymic`, `last_name`), дата рождения (`birth_date`) или серия и номер паспорта (`persondoc_number`), возвращается ошибка `USER_PERSONDOC_REQUIRED` (HTTP 400).

Ответ `UserKYCResponse`:
```json
{
  "user_id": 1,
  "kyc_status": true,
  "kyc_level": "40",
  "provider_status": "APPROVED",
  "persondoc_result": "300",
  "identification_level": "40",
  "persondoc_fail_reason": null,
  "updated_at": "2026-09-26T12:00:00Z"
}
```
Значения полей провайдера:
- `kyc_status`: `true`, если `provider_status == "APPROVED"` и `kyc_level` равен `"20"` или `"40"`.
- `identification_level` / `kyc_level`: `"40"` (полная идентификация), `"20"` (упрощенная идентификация), `"0"` (идентификация отсутствует).
- `persondoc_result`: `"300"` (паспорт действителен), `"301"` (паспорт недействителен), `"302"` (паспорт не найден).
- `persondoc_fail_reason`: `"601"` (не найден в реестре), `"602"` (числится недействительным), `"604"` (данные не соответствуют).

## Client endpoints

- `GET /api/v1/client/order_link` - возвращает ссылку на экран сделки по `order_id`.
- `GET /api/v1/client/order_info_by_slug` - возвращает информацию о сделке по `slug`.
- `GET /api/v1/client/order_info` - возвращает информацию о сделке по `order_id`.
- `GET /api/v1/client/deals` - возвращает активные сделки заказчика.
- `POST /api/v1/client/deal_create` - создает сделку и регистрирует депозитную операцию в Paygine.
- `POST /api/v1/client/deal_confirm` - завершает payment flow и запускает payout flow.
- `POST /api/v1/client/deal_softdecline` - отменяет неоплаченную сделку или регистрирует возврат и переводит сделку в `awaiting_client_payout`.
- `POST /api/v1/client/deal_harddecline` - переводит сделку в `awaiting_conflict`.
- `GET /api/v1/client/deal_payment_link` - возвращает signed Paygine URL для оплаты сделки.
- `GET /api/v1/client/deals_archive` - возвращает закрытые сделки заказчика.

Создание сделки (`POST /api/v1/client/deal_create`):

- входной контракт `CreateOrderRequest` принимает:
  - `order_type` (обязательное) - тип сделки (`subscriptions`, `tickets_and_reservations`, `free_deal`);
  - `title` (обязательное) - название сделки;
  - `customer_email` (обязательное) - email заказчика для платежных уведомлений;
  - `price` (обязательное) - сумма сделки в рублях;
  - `expire_in` (обязательное) - дата и время дедлайна сделки (ISO 8601);
  - `violation_proof_requirements` (обязательное) - требования к доказательствам нарушений (варианты flexbox через запятую + пользовательский ввод);
  - `source_of_truth` (опционально) - источник истины для разрешения споров;
  - `site_or_app` (опционально) - официальный сайт или приложение;
  - `customer_identity` (опционально) - идентификатор заказчика (ID аккаунта, логин, ФИО);
  - `additional_requirements` (опционально) - текст дополнительных требований;
  - `contact_free_deal` (опционально, для свободной сделки) - контакт/источник проверки результата;
  - `task_free_deal` (опционально, для свободной сделки) - описание задачи;
  - `how_to_proove_free_deal` (опционально, для свободной сделки) - что докажет выполнение задачи;
- проверяет существование пользователя;
- проверяет сумму сделки и статус верификации заказчика (до 15 000 руб. — без ограничений; от 15 000 до 100 000 руб. — требует подтвержденной KYC-верификации в `kyc_data` с `kyc_status == true`, иначе возвращается ошибка `USER_VERIFICATION_REQUIRED`; свыше 100 000 руб. — запрещено с ошибкой `ORDER_PRICE_LIMIT_EXCEEDED`);
- проверяет месячный лимит суммы сделок через `User.month_sum_limit`;
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
- `deal_softdecline` вызывает `ChangeOrderStatus` с `EXPIRED` для неоплаченной сделки или регистрирует refund-операцию и переводит оплаченную сделку в `awaiting_client_payout`.
- `deal_harddecline` не затрагивает Paygine и переводит сделку в конфликт.

## Performer endpoints

- `GET /api/v1/performer/deals` - возвращает активные сделки исполнителя.
- `POST /api/v1/performer/deal_approve` - назначает исполнителя и переводит сделку в `awaiting_payment`.
- `POST /api/v1/performer/deal_confirm` - переводит сделку в `awaiting_client_confirmation`.
- `POST /api/v1/performer/deal_decline` - отменяет неоплаченную сделку или регистрирует возврат и переводит сделку в `awaiting_client_payout`.
- `POST /api/v1/performer/deal_conflict` - переводит сделку в `open_conflict`.
- `GET /api/v1/performer/deal_payout_link` - возвращает signed Paygine URL для получения средств.
- `GET /api/v1/client/deal_refund_link` - возвращает signed Paygine URL для получения возврата заказчиком.
- `GET /api/v1/performer/deals_archive` - возвращает закрытые сделки исполнителя.

Исполнитель не может принять или выполнять действия по собственной сделке. Если `client_id` сделки совпадает с `user_id` исполнителя, возвращается `ORDER_SELF_EXECUTION_FORBIDDEN`.

Принять можно только сделку в статусе `awaiting_performer` и без назначенного исполнителя. Если сделка уже принята или находится в неподходящем статусе, возвращается `ORDER_ALREADY_ACCEPTED`.

Платежные эффекты исполнительских endpoint-ов:

- `deal_approve` сохраняет `performer_email` в `orders_payment_data` и переводит сделку в `awaiting_payment`.
- `deal_decline` регистрирует возврат заказчику без сервисной комиссии, сохраняет `paygine_revoked_operation_id` и переводит сделку в `awaiting_client_payout`.
- `deal_payout_link` использует `paygine_payout_operation_id` и строит ссылку на `SDPayOutPage`.
- `deal_refund_link` использует `paygine_revoked_operation_id` и строит ссылку на `SDPayOutPage`.

## Admin endpoints

- `POST /api/v1/admin/login` - авторизация администратора по email и паролю. При включенном 2FA возвращает `pre_auth_token`, иначе access token + refresh token.
- `POST /api/v1/admin/logout` - отзыв refresh token администратора.
- `POST /api/v1/admin/2fa/setup` - генерация секрета, QR-кода и резервных кодов для настройки 2FA администратора.
- `POST /api/v1/admin/2fa/enable` - активация 2FA администратора по TOTP коду.
- `POST /api/v1/admin/2fa/verify` - завершение входа администратора по `pre_auth_token` и коду (TOTP или backup).
- `POST /api/v1/admin/2fa/disable` - отключение 2FA администратора (требует пароль и код).
- `GET /api/v1/admin/2fa/status` - статус 2FA и остаток резервных кодов администратора.
- `GET /api/v1/admin/orders` - постраничный список сделок с фильтрацией по пользователям, статусу и датам.
- `GET /api/v1/admin/users` - постраничный список пользователей с агрегированной статистикой сделок.
- `GET /api/v1/admin/order_info` - полная информация о сделке и история статусов.
- `GET /api/v1/admin/get_balance` - получение баланса кубышки платформы.
- `POST /api/v1/admin/ban_user` - блокировка пользователя с сохранением причины.
- `POST /api/v1/admin/orders/{order_id}/close_to_client` - закрытие спора в пользу заказчика и регистрация возврата. Требует обязательное тело `{"reason": "Причина решения арбитра"}`.
- `POST /api/v1/admin/orders/{order_id}/close_to_performer` - закрытие спора в пользу исполнителя и регистрация выплаты. Требует обязательное тело `{"reason": "Причина решения арбитра"}`.

## Платежный контур

Подробная реализация платежных запросов и webhook-ов описана в:

- [payments.md](payments.md)
- [webhooks.md](webhooks.md)

Ключевые внешние события:

- `POST /api/v1/client/deal_create` - регистрация депозитной сделки.
- `POST /api/v1/client/deal_confirm` - завершение платежа и регистрация payout.
- `POST /api/v1/admin/orders/{order_id}/close_to_client` - закрытие спора в пользу заказчика и возврат средств (реверс при AUTHORIZED, выплата при COMPLETED) с фиксацией `reason`.
- `POST /api/v1/admin/orders/{order_id}/close_to_performer` - закрытие спора в пользу исполнителя и регистрация payout (с завершением списания при AUTHORIZED) с фиксацией `reason`.
- `POST /v1/paygine/webhook_order_status` - синхронизация статусов операций Paygine с БД.

## Статусы сделок

Активные статусы:

- `awaiting_performer`
- `awaiting_payment`
- `awaiting_performer_confirmation`
- `awaiting_client_confirmation`
- `awaiting_performer_payout`
- `awaiting_client_payout`
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
- `changed_by_admin_id`
- `comment`

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
