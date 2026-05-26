from fastapi import APIRouter

from api.utils.orders_methods import get_order_link


router = APIRouter()


@router.get("/order_link")
async def order_link(order_id: int) -> dict[str, str]:
    return {"link": await get_order_link(order_id)}

@router.get("/order_info")
async def order_info() -> None:
    pass

@router.get("/deals")
async def deals() -> None:
    pass


@router.post("/deal_create")
async def deal_create() -> None:
    pass


@router.post("/deal_payment")
async def deal_payment() -> None:
    pass


@router.post("/deal_confirm")
async def deal_confirm() -> None:
    pass


@router.post("/deal_softdecline")
async def deal_softdecline() -> None:
    pass


@router.post("/deal_harddecline")
async def deal_harddecline() -> None:
    pass


@router.post("/deal_conflict")
async def deal_conflict() -> None:
    pass


@router.get("/deals_archive")
async def deals_archive() -> None:
    pass
