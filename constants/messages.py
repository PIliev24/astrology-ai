"""
User-facing messages and error strings.

Centralized location for all UI messages to ensure consistency
and make internationalization easier in the future.
"""


class ErrorMessages:
    """Error messages returned to clients."""

    # Authentication
    AUTHENTICATION_REQUIRED = "Authentication required"
    INVALID_CREDENTIALS = "Invalid authentication credentials"
    TOKEN_EXPIRED = "Authentication token has expired"
    AUTH_SERVICE_NOT_CONFIGURED = "Authentication service not configured"
    COULD_NOT_VALIDATE_CREDENTIALS = "Could not validate credentials"

    # Resources
    CHART_NOT_FOUND = "Birth chart not found"
    CONVERSATION_NOT_FOUND = "Conversation not found"
    SUBSCRIPTION_NOT_FOUND = "Subscription not found"
    MESSAGE_NOT_FOUND = "Message not found"

    # Rate Limiting
    MESSAGE_LIMIT_EXCEEDED = "Daily message limit reached. Consider upgrading to Pro for unlimited messages."
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded. Please try again later."

    # External Services
    EXTERNAL_SERVICE_ERROR = "External service temporarily unavailable"
    ASTROLOGY_API_ERROR = "Error calculating birth chart. Please try again."
    PAYMENT_ERROR = "Payment processing error. Please try again."
    LOCATION_SERVICE_ERROR = "Location service temporarily unavailable"

    # Validation
    INVALID_REQUEST = "Invalid request format"
    INVALID_DATE_FORMAT = "Invalid date format. Expected: dd-mmm-yyyy hh:mm (e.g., 15-Jan-1990 14:30)"
    INVALID_LOCATION = "Could not resolve the specified location"
    MISSING_REQUIRED_FIELD = "Missing required field: {field}"

    # Subscription
    NO_ACTIVE_SUBSCRIPTION = "No active subscription found"
    SUBSCRIPTION_ALREADY_CANCELLED = "Subscription is already cancelled"
    CANNOT_REACTIVATE = "Cannot reactivate subscription"

    # WebSocket
    WEBSOCKET_AUTH_FAILED = "WebSocket authentication failed"
    WEBSOCKET_CONNECTION_ERROR = "WebSocket connection error"

    # Internal
    INTERNAL_ERROR = "An unexpected error occurred"
    DATABASE_ERROR = "Database operation failed"
    CONFIGURATION_ERROR = "Service configuration error"


class SuccessMessages:
    """Success messages returned to clients."""

    # Authentication
    USER_REGISTERED = "User registered successfully. Please check your email to confirm your account."
    LOGIN_SUCCESS = "Login successful"
    LOGOUT_SUCCESS = "Logged out successfully"
    TOKEN_REFRESHED = "Token refreshed successfully"

    # Birth Chart
    CHART_CREATED = "Birth chart created successfully"
    CHART_DELETED = "Birth chart deleted successfully"
    CHART_UPDATED = "Birth chart updated successfully"

    # Conversation
    CONVERSATION_CREATED = "Conversation started"
    CONVERSATION_DELETED = "Conversation deleted successfully"
    MESSAGE_SENT = "Message sent successfully"

    # Subscription
    SUBSCRIPTION_CREATED = "Subscription created successfully"
    SUBSCRIPTION_CANCELLED = "Subscription cancelled successfully"
    SUBSCRIPTION_REACTIVATED = "Subscription reactivated successfully"
    CHECKOUT_CREATED = "Checkout session created"

    # General
    OPERATION_SUCCESSFUL = "Operation completed successfully"
