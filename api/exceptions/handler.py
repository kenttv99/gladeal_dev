import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import httpx
from sqlalchemy.exc import SQLAlchemyError
from xml.etree.ElementTree import ParseError

from api.exceptions.exceptions import BaseAPIException
from api.exceptions.i18n import translate


logger = logging.getLogger(__name__)


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
    logger.exception(
        "Unhandled exception: %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    lang = request.headers.get("accept-language")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": translate(lang, "INTERNAL_SERVER_ERROR")
        }
    )


async def payment_provider_exception_handler(request: Request, exc: httpx.HTTPError) -> JSONResponse:
    logger.exception(
        "Payment provider request failed: %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    lang = request.headers.get("accept-language")
    error_code = "PAYMENT_REGISTER_DEAL_FAILED"
    return JSONResponse(
        status_code=502,
        content={
            "error": error_code,
            "message": translate(lang, error_code),
        },
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception(
        "Database error: %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    lang = request.headers.get("accept-language")
    details = getattr(exc, "payment_data", None)
    error_code = "PAYMENT_DATA_SAVE_FAILED" if details else "INTERNAL_SERVER_ERROR"
    content = {
        "error": error_code,
        "message": translate(lang, error_code),
    }
    if details:
        content["details"] = details
    return JSONResponse(status_code=500, content=content)


async def xml_parse_exception_handler(request: Request, exc: ParseError) -> JSONResponse:
    lang = request.headers.get("accept-language")
    error_code = "PAYMENT_INVALID_PROVIDER_RESPONSE"
    return JSONResponse(
        status_code=502,
        content={
            "error": error_code,
            "message": translate(lang, error_code),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BaseAPIException, api_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(httpx.HTTPError, payment_provider_exception_handler)  # type: ignore
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)  # type: ignore
    app.add_exception_handler(ParseError, xml_parse_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, global_exception_handler)
