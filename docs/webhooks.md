# Webhooks Paygine

Webhook-обработчики Paygine вынесены в отдельное FastAPI-приложение `api/servers/payments.py`. Этот сервис принимает callback-и о состоянии платежей.

## Стек

- FastAPI - HTTP endpoint-ы webhook-ов и redirect-ов.
- SQLAlchemy async - атомарное обновление `orders` и `orders_payment_data`.
- XML parser - разбор payload Paygine.
- PostgreSQL row locks - защита от повторной обработки одной операции несколькими процессами.

## Структура

- `api/servers/payments.py` - отдельное приложение для webhook-ов Paygine.
- `api/webhooks/v1/order_status_webhook.py` - обработка статусов платежных операций.
- `api/utils/order_status_webhook_methods.py` - бизнес-логика обновления заказа по callback-у.
- `api/payments/auth_methods.py` - проверка цифровой подписи Paygine.
- `api/payments/utils/xml_response_parser.py` - разбор XML тела запроса.
- `database/models/orders.py` - статус сделки и история статусов.
- `database/models/payments.py` - платежные статусы и ids Paygine-операций.
- `api/enums/enums_v1.py` - статусы заказов и платежей.

## Эндпоинты

Сервис поднимается отдельно от основного API и использует порт `8001`.

- `POST /v1/paygine/webhook_order_status` - callback Paygine по статусу операции.
- `GET /v1/paygine/redirect/success` - redirect после успешного перехода пользователя.
- `GET /v1/paygine/redirect/failure` - redirect после неудачного перехода пользователя.

## Callback по статусу операции

`webhook_order_status`:

- читает raw XML body из `Request`;
- логирует полученный payload;
- парсит payload в dict;
- проверяет `data.signature` по листовым XML-значениям без поля `signature`;
- нормализует `data.order_state` в `OrderPaymentStates`;
- определяет тип операции по `data.reference` и `data.order_id`;
- обновляет `orders` и `orders_payment_data` в одной транзакции.

Формат `reference`, который использует код:

- `gladeal-order-{order_id}` - депозитная операция;
- `gladeal-order-{order_id}-payout` - payout-операция.
- `gladeal-order-{order_id}-refund` - возвратная payout-операция заказчику.

Тип операции определяется по совпадению `data.order_id` с сохраненными:

- `paygine_payment_operation_id`;
- `paygine_payout_operation_id`.
- `paygine_revoked_operation_id`.

Если payload не соответствует ожидаемой структуре, выбрасывается `PaymentInvalidProviderResponseError`.
Если `signature` отсутствует или не совпадает с расчетной подписью, выбрасывается `PaymentInvalidProviderSignatureError`.

## Обработка payment callback

Для депозитной операции:

- `AUTHORIZED` - вызывается `complete_paymented_deal`, `orders_payment_data.payment_status = authorized`.
- `COMPLETED` - `orders_payment_data.payment_status = completed`, `payment_complete_at = now()`, `orders.status = awaiting_performer_confirmation`, запись добавляется в `order_status_history`.

Для payout-операции:

- `COMPLETED` - `orders_payment_data.payout_status = completed`, `payout_completed_at = now()`, запись добавляется в `order_status_history`.

Для refund-операции:

- `COMPLETED` - `orders_payment_data.revoke_status = completed`, `revoked_at = now()`, сделка переводится из `awaiting_client_payout` в `unsuccessful_completion`, запись добавляется в `order_status_history`.

Статус сделки при `COMPLETED` payout выбирается по текущему бизнес-исходу:

- обычная выплата исполнителю из `awaiting_performer_payout` переводит сделку в `successful_completion`;
- выплата по просрочке сохраняет `confirm_by_expire_time_to_performer`;
- возврат после успешного вывода заказчиком переводит сделку в `unsuccessful_completion`.

Другие допустимые значения `OrderPaymentStates` сейчас проходят через парсер и возвращаются в ответе, но отдельной бизнес-логики для них нет.

## Ответ webhook

Успешный ответ `POST /v1/paygine/webhook_order_status`:

```json
{
  "status": "accepted",
  "order_state": "authorized"
}
```

Фактическое значение `order_state` зависит от payload Paygine.

## Связь с платежным контуром

Webhook-слой работает вместе с методами из [payments.md](payments.md):

- регистрация депозитной сделки на этапе создания заказа;
- регистрация payout-операции после подтверждения клиентом;
- регистрация возврата средств при отказе исполнителя или при просрочке;
- завершение payout-операции после выплаты исполнителю.
