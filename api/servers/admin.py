import uvicorn
from fastapi import FastAPI

from api.endpoints.v1.admins_endpoints import router as admins_router
from api.exceptions import register_exception_handlers


app = FastAPI(
    title="GLADEAL Admin API",
    description="API для административных методов",
    version="1.0.0",
)

register_exception_handlers(app)

app.include_router(
    admins_router,
    prefix="/api/v1/admins",
    tags=["Admins"],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)

