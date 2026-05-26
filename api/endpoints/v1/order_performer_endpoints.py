from fastapi import APIRouter


router = APIRouter()


@router.get("/deals")
async def deals() -> None:
    pass


@router.post("/deal_approve")
async def deal_approve() -> None:
    pass


@router.post("/deal_confirm")
async def deal_confirm() -> None:
    pass


@router.post("/deal_decline")
async def deal_decline() -> None:
    pass


@router.post("/deal_conflict")
async def deal_conflict() -> None:
    pass


@router.get("/deals_archive")
async def deals_archive() -> None:
    pass
