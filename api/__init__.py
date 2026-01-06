"""API module with all routers."""

# Import routers - these are kept in their original locations
# The feature directories (api/birth_chart/, api/conversation/, etc.) contain
# services and schemas, not routers (routers will be migrated later)

# Note: These imports use the existing router modules
# Auth router
from api import auth
# Other routers
from api import birth_chart_router
from api import conversation_router
from api import subscription_router
from api import webhook_router
from api import websocket_router

__all__ = [
    "auth",
    "birth_chart_router",
    "conversation_router",
    "subscription_router",
    "webhook_router",
    "websocket_router",
]
