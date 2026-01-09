"""
Custom exception hierarchy for the application.

All exceptions inherit from AppException, which provides a consistent structure
for error responses. Domain-specific exceptions should inherit from the
appropriate base exception (NotFoundError, ValidationError, etc.).

Usage:
    raise ChartNotFoundError()
    raise ChartNotFoundError("Custom message")
    raise ChartNotFoundError(details={"chart_id": "123"})
"""

from typing import Any, Optional


class AppException(Exception):
    """
    Base application exception.

    All custom exceptions should inherit from this class.
    The exception handler will convert these to consistent JSON responses.

    Attributes:
        status_code: HTTP status code to return
        error_code: Machine-readable error identifier
        message: Human-readable error message
        details: Additional error context (optional)
    """

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Any] = None,
    ):
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


# Base HTTP Exceptions

class NotFoundError(AppException):
    """Resource not found (404)."""
    status_code = 404
    error_code = "not_found"
    message = "Resource not found"


class UnauthorizedError(AppException):
    """Authentication required or failed (401)."""
    status_code = 401
    error_code = "unauthorized"
    message = "Authentication required"


class ForbiddenError(AppException):
    """Access denied to resource (403)."""
    status_code = 403
    error_code = "forbidden"
    message = "Access denied"


class ValidationError(AppException):
    """Request validation failed (422)."""
    status_code = 422
    error_code = "validation_error"
    message = "Validation failed"


class ExternalServiceError(AppException):
    """External service unavailable (502)."""
    status_code = 502
    error_code = "external_service_error"
    message = "External service unavailable"


class TimeoutError(AppException):
    """Request timed out (504)."""
    status_code = 504
    error_code = "timeout"
    message = "Request timed out"


class RateLimitError(AppException):
    """Rate limit exceeded (429)."""
    status_code = 429
    error_code = "rate_limit_exceeded"
    message = "Rate limit exceeded"


class ConflictError(AppException):
    """Resource conflict (409)."""
    status_code = 409
    error_code = "conflict"
    message = "Resource conflict"


class BadRequestError(AppException):
    """Bad request (400)."""
    status_code = 400
    error_code = "bad_request"
    message = "Bad request"


# Domain-Specific Exceptions

class ChartNotFoundError(NotFoundError):
    """Birth chart not found."""
    error_code = "chart_not_found"
    message = "Birth chart not found"


class ConversationNotFoundError(NotFoundError):
    """Conversation not found."""
    error_code = "conversation_not_found"
    message = "Conversation not found"


class SubscriptionNotFoundError(NotFoundError):
    """Subscription not found."""
    error_code = "subscription_not_found"
    message = "Subscription not found"


class MessageLimitExceededError(RateLimitError):
    """Daily message limit reached."""
    error_code = "message_limit_exceeded"
    message = "Daily message limit reached. Consider upgrading to Pro for unlimited messages."


class InvalidCredentialsError(UnauthorizedError):
    """Invalid authentication credentials."""
    error_code = "invalid_credentials"
    message = "Invalid authentication credentials"


class TokenExpiredError(UnauthorizedError):
    """Authentication token has expired."""
    error_code = "token_expired"
    message = "Authentication token has expired"


class LocationNotFoundError(BadRequestError):
    """Location could not be resolved."""
    error_code = "location_not_found"
    message = "Could not resolve the specified location"


class InvalidDateFormatError(BadRequestError):
    """Date format is invalid."""
    error_code = "invalid_date_format"
    message = "Invalid date format"


class AstrologyAPIError(ExternalServiceError):
    """Error from astrology calculation API."""
    error_code = "astrology_api_error"
    message = "Error calculating birth chart"


class StripeError(ExternalServiceError):
    """Error from Stripe API."""
    error_code = "stripe_error"
    message = "Payment processing error"
