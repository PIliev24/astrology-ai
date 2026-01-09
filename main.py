import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config.settings import get_settings
from core.error_handlers import register_exception_handlers
from api import (
    birth_chart_router,
    auth,
    websocket_router,
    conversation_router,
    subscription_router,
    webhook_router,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load and validate settings at startup
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Astrology API",
    description="AI-powered astrology API with birth chart calculations and chat",
    version="1.0.0",
)

# Register custom exception handlers
register_exception_handlers(app)

# Configure CORS from settings
allowed_origins = settings.cors_origins
logger.info("Configured CORS for origins: %s", allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("Application startup complete")

# Include all routers
# Auth router (public endpoints)
app.include_router(auth.router)

# Protected astrology endpoints
app.include_router(birth_chart_router.router)

# Conversation management endpoints
app.include_router(conversation_router.router)

# WebSocket router for AI assistant chat
app.include_router(websocket_router.router)

# Subscription management endpoints
app.include_router(subscription_router.router)

# Stripe webhook endpoints
app.include_router(webhook_router.router)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

