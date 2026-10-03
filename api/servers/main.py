from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.endpoints.v1.order_client_endpoints import router as order_client_router
from api.endpoints.v1.order_performer_endpoints import router as order_performer_router
from api.endpoints.v1.users_endpoints import router as users_router
from api.exceptions import register_exception_handlers
from api.payments.http_client import close_paygine_client
from api.utils.jwt_methods import authorize_user




@asynccontextmanager
async def lifespan(app: FastAPI):
    """Закрываем внешние async-клиенты при остановке приложения."""
    yield
    await close_paygine_client()


app = FastAPI(
    title='GLADEAL API',
    description='API для взаимодействия с backend',
    version='1.0.0',
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене конкретные домены/API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Подключаем роутеры с префиксами и тегами
app.include_router(users_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(
    order_client_router,
    prefix="/api/v1/client",
    tags=["Client orders"],
    dependencies=[Depends(authorize_user)],
)
app.include_router(
    order_performer_router,
    prefix="/api/v1/performer",
    tags=["Performer orders"],
    dependencies=[Depends(authorize_user)],
)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
