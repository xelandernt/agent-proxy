from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.exceptions import HTTPException

from proxy.app.inference.schemas import OpenAIErrorBody, OpenAIErrorEnvelope

logger = logging.getLogger(__name__)


class OpenAIErrorException(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        error_type: str,
        param: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = OpenAIErrorBody(
            message=message,
            type=error_type,
            param=param,
            code=code,
        )


def error_response(error: OpenAIErrorException) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=OpenAIErrorEnvelope(error=error.body).model_dump(mode="json"),
        headers=({"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None),
    )


async def openai_error_handler(
    _request: Request, error: OpenAIErrorException
) -> JSONResponse:
    return error_response(error)


async def openai_validation_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    if not request.url.path.startswith("/v1/"):
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, error)
    first = error.errors()[0] if error.errors() else {}
    location = first.get("loc", ())
    param = str(location[-1]) if location else None
    message = str(first.get("msg", "Invalid request."))
    return error_response(
        OpenAIErrorException(
            400,
            message,
            error_type="invalid_request_error",
            param=param,
            code="invalid_request",
        )
    )


async def openai_http_error_handler(
    request: Request,
    error: HTTPException,
) -> Response:
    if not request.url.path.startswith("/v1/"):
        return await http_exception_handler(request, error)
    return error_response(
        OpenAIErrorException(
            error.status_code,
            str(error.detail),
            error_type="invalid_request_error",
            code="not_found" if error.status_code == 404 else "http_error",
        )
    )


async def openai_unhandled_error_handler(
    request: Request,
    error: Exception,
) -> Response:
    if not request.url.path.startswith("/v1/"):
        return PlainTextResponse("Internal Server Error", status_code=500)
    logger.error("Unhandled model gateway error: %s", type(error).__name__)
    return error_response(
        OpenAIErrorException(
            500,
            "The model gateway encountered an internal error.",
            error_type="server_error",
            code="internal_error",
        )
    )
