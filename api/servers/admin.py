import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints.v1.admins_endpoints import router as admins_router
from api.exceptions import register_exception_handlers


app = FastAPI(
    title="GLADEAL Admin API",
    description="API для административных методов",
    version="1.0.0",
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

app.include_router(
    admins_router,
    prefix="/api/v1/admin",
    tags=["Admins"],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)

