from api.payments.utils.register_deal_methods import (
    DealParticipant,
    RegisterDealRequest,
    RegisterDealResponse,
    send_register_deal_request,
)


async def register_deal(
    customer: DealParticipant,
    performer: DealParticipant,
    amount: int,
    reference: str,
    description: str,
    currency: int = 643,
    fee: int | None = None,
    url: str | None = None,
    failurl: str | None = None,
    life_period: int | None = None,
    sd_ref: str | None = None,
    notify_url: str | None = None,
    mode: int = 0,
) -> RegisterDealResponse:
    return await send_register_deal_request(
        RegisterDealRequest(
            customer=customer,
            performer=performer,
            amount=amount,
            currency=currency,
            reference=reference,
            description=description,
            fee=fee,
            url=url,
            failurl=failurl,
            life_period=life_period,
            sd_ref=sd_ref,
            notify_url=notify_url,
            mode=mode,
        )
    )


async def freeze_money() -> None:
    pass


async def withdrow_to_performer() -> None:
    pass


async def refund_money() -> None:
    pass


async def revoke_deal() -> None:
    pass


async def calculate_comissions() -> None:
    pass


async def status_handle() -> None:
    pass
