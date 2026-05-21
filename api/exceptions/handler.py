from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from api.exceptions.exceptions import BaseAPIException
from api.exceptions.i18n import translate


async def api_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    lang = request.headers.get("accept-language")
    message = translate(lang, exc.error_code)
    
    content = {"error": exc.error_code, "message": message}
    if exc.details:
        content["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    lang = request.headers.get("accept-language")
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": translate(lang, "VALIDATION_ERROR"),
            "details": exc.errors()
        }
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    lang = request.headers.get("accept-language")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": translate(lang, "INTERNAL_SERVER_ERROR")
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BaseAPIException, api_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, global_exception_handler)
