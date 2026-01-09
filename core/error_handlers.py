"""
FastAPI exception handlers for consistent error responses.

Registers handlers for AppException and its subclasses to return
consistent JSON error responses across all endpoints.
"""

import logging
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import AppException

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle AppException and return consistent JSON response.

    Args:
        request: The incoming request
        exc: The exception that was raised

    Returns:
        JSONResponse with error details
    """
    # Log the error (with details for debugging)
    log_message = f"{exc.error_code}: {exc.message}"
    if exc.details:
        log_message += f" | Details: {exc.details}"

    if exc.status_code >= 500:
        logger.error(log_message, exc_info=True)
    else:
        logger.warning(log_message)

    content = {
        "error": exc.error_code,
        "message": exc.message,
    }

    # Only include details if present
    if exc.details is not None:
        content["details"] = exc.details

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions to prevent leaking internal details.

    Args:
        request: The incoming request
        exc: The exception that was raised

    Returns:
        JSONResponse with generic error message
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
        },
    )


def register_exception_handlers(app: "FastAPI") -> None:
    """
    Register all exception handlers with the FastAPI application.

    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(AppException, app_exception_handler)
    # Optionally catch all unhandled exceptions
    # app.add_exception_handler(Exception, generic_exception_handler)
