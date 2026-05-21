from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn




app = FastAPI(
    title='GLADEAL API',
    description='API для взаимодействия с backend',
    version='1.0.0'
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры с префиксами и тегами


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)