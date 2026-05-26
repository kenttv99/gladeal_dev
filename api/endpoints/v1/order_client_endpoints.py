from fastapi import APIRouter


router = APIRouter()


@router.get("/order_link")
async def order_link() -> None:
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
