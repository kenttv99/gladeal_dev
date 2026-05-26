from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.endpoints.v1.users_endpoints import router as users_router
from api.exceptions import register_exception_handlers




app = FastAPI(
    title='GLADEAL API',
    description='API для взаимодействия с backend',
    version='1.0.0'
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
app.include_router(users_router, prefix="/api/v1/client", tags=["Auth"])


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
