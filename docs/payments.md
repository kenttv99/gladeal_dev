# Платежный контур

Платежный слой проекта состоит из сервисных методов `api/payments/*` и отдельного FastAPI-приложения `api/servers/payments.py`. Этот контур отвечает за регистрацию платежных операций в Paygine, генерацию ссылок оплаты и выплат, а также за обработку ответов провайдера.

## Стек

- FastAPI - webhook- и redirect-эндпоинты Paygine.
- `httpx.AsyncClient` - асинхронные запросы к Paygine.
- SQLAlchemy async - запись и чтение платежных данных при работе с заказами.
- Pydantic - контракты запросов и ответов.
- XML parser - нормализация ответов Paygine.
- SHA-256 + base64 - подписи исходящих запросов.

## Структура

- `api/payments/config.py` - загрузка `.env.payments` и валидация платежных переменных.
- `api/payments/auth_methods.py` - построение и проверка signature.
- `api/payments/http_client.py` - общий асинхронный клиент Paygine.
- `api/payments/utils/commission_methods.py` - расчёт комиссии и перевод сумм в копейки.
- `api/payments/utils/register_deal_methods.py` - регистрация депозитных и payout-сделок.
- `api/payments/utils/generate_payment_link_methods.py` - генерация ссылки оплаты.
- `api/payments/utils/generate_withdrow_link_methods.py` - генерация ссылки выплаты исполнителю.
- `api/payments/utils/complete_paymented_deal_methods.py` - завершение оплаченной сделки.
- `api/payments/utils/cancle_unpayment_deal_methods.py` - перевод неоплаченной сделки в `EXPIRED`.
- `api/payments/utils/refund_money_methods.py` - регистрация возврата средств заказчику.
- `api/payments/payments_methods.py` - публичный фасад для API и воркеров.
- `api/schemas/schemas_v1.py` - payment request/response модели.
- `api/servers/payments.py` - отдельное приложение для webhook-ов Paygine.

## Конфигурация

Параметры платежного контура загружаются из `.env.payments`.

- `PAYGINE_BASE_URL` - базовый URL Paygine и источник для генерации ссылок.
- `PAYGINE_SECTOR` - идентификатор сектора.
- `PAYGINE_SIGNATURE_PASSWORD` - пароль для подписи запросов.
- `SR_REF` - референс paygine sd-ref.
- `DEAL_FEE_PERCENT` - процент комиссии проекта.
- `EXPIRES_PAYMENT_TIME_MINUTES` - срок жизни платежной операции.
- `EXPIRES_PAYOUT_TIME_MINUTES` - срок жизни payout-операции.
- `PAYGINE_REQUEST_TIMEOUT_SECONDS` - таймаут HTTP-клиента, в коде задан как `30`.

Если обязательная переменная отсутствует, модуль `api/payments/config.py` завершает загрузку с `RuntimeError`.

## Подписи и ответы

Подпись строится из последовательности значений и пароля:

`base64(sha256("".join(values) + password).hexdigest())`

Проверка подписи использует `compare_digest`.

Все ответы Paygine проходят через `parse_paygine_response`:

- XML превращается в `dict` с полями `root_tag` и `data`.
- не-XML ответ сохраняется как текстовый `root_tag = "text"`.
- некорректный XML вызывает `PaymentInvalidProviderResponseError`.

## Регистрация сделок

### Депозитная сделка

Метод `create_deposit_deal`:

- собирает backend-контракт `RegisterDepositDealPaymentRequest`;
- вычисляет сумму заказа и комиссию в копейках;
- отправляет `POST /webapi/Register`;
- строит `notify_url` на основе `BASE_SITE_LINK` и пути `/v1/paygine/webhook_order_status`;
- возвращает `RegisterDepositDealPaymentResponse`.

В payload для Paygine используются:

- `sector`
- `amount`
- `currency`
- `sd_ref`
- `reference = gladeal-order-{order_id}`
- `description`
- `notify_url`
- `payer_id`
- `email`
- `phone`

В `orders_payment_data` сохраняются:

- `currency`
- `order_amount`
- `service_fee_amount`
- `paygine_payment_operation_id`
- `expire_payment_at`

### Payout-сделка

Метод `create_payout_deal`:

- собирает backend-контракт `RegisterPayoutDealPaymentRequest`;
- формирует provider-контракт с `client_ref` исполнителя;
- отправляет `POST /webapi/Register`;
- возвращает `RegisterPayoutDealPaymentResponse`.

В payload для Paygine используются:

- `sector`
- `amount` без комиссии
- `currency`
- `sd_ref`
- `reference = gladeal-order-{order_id}-payout`
- `description`
- `notify_url`
- `client_ref`
- `email`
- `phone`

В `orders_payment_data` сохраняются:

- `paygine_payout_operation_id`
- `expire_payout_at`

## Ссылки Paygine

### Оплата

Метод `generate_payment_link` строит signed URL на основе:

- `/webapi/b2puser/sd-services/SDPayInDebit`
- `sector`
- `id`
- `sd_ref`

### Выплата исполнителю

Метод `generate_withdrow_link` строит signed URL на основе:

- `/webapi/b2puser/sd-services/SDPayOutPage`
- `sector`
- `id`
- `sd_ref`

## Операции завершения

- `complete_paymented_deal` вызывает `POST /webapi/b2puser/sd-services/SDComplete`.
- `refund_money` регистрирует payout-операцию возврата через `POST /webapi/Register` с `client_ref` заказчика и суммой заказа без сервисной комиссии.
- `cancle_unpayment_deal` вызывает `POST /webapi/ChangeOrderStatus` с `order_state=EXPIRED`.

Все эти методы используют общий `httpx.AsyncClient` и парсят ответ через `parse_paygine_response`.

## Взаимодействие с заказами

Платежный слой не является набором HTTP-эндпоинтов. Он вызывается из:

- `api/utils/orders_methods.py` - создание сделки, подтверждение клиентом, отказ исполнителя и soft decline.
- `workers/utils/order_expire_methods.py` - обработка просроченных сделок.
- `api/webhooks/v1/order_status_webhook.py` - обработка callback-ов Paygine.

Именно через этот слой в `orders_payment_data` попадают `paygine_payment_operation_id`, `paygine_payout_operation_id`, `paygine_revoked_operation_id`, статусы операций и сроки их истечения.
