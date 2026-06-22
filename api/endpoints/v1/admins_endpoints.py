from fastapi import APIRouter, Body, Depends


router = APIRouter()


@router.get("/get_users")
async def get_users():
    pass

@router.get("/get_orders")
async def get_orders():
    pass

@router.get("/get_order_info")
async def get_order_info():
    pass

@router.get("/get_balance")
async def get_balance():
    pass

@router.get("/close_to_client")
async def close_to_client():
    pass

@router.get("/close_to_performer")
async def close_to_performer():
    pass


@router.get("/ban_user")
async def ban_user():
    pass


@router.get("/unban_user")
async def unban_user():
    pass

