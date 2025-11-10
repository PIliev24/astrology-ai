from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from api import (
    birth_chart_router,
    aspects_router,
    charts_router,
    relationships_router,
    auth,
)
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()
load_dotenv()

# Allow your frontend domain in production + localhost for development
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add your production frontend URL if you have one
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

logger.info(f"Configured CORS for origins: {allowed_origins}")

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
app.include_router(aspects_router.router)
app.include_router(charts_router.router)
app.include_router(relationships_router.router)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

