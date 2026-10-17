import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend_service.api.routes import router as api_router
from backend_service.config import get_settings

settings = get_settings()

# Configure logging according to backend style guide
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aisle.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing AIsle Backend Service (Env: %s)", settings.ENVIRONMENT)
    logger.info("Target GCP Project: %s, Region: %s", settings.GCP_PROJECT_ID, settings.GCP_REGION)
    yield
    logger.info("Shutting down AIsle Backend Service...")


app = FastAPI(
    title="AIsle - Intelligent Retail Behavioral Analytics Engine",
    description=(
        "Next-generation physical retail analytics pipeline powered by Google Gemini 1.5 "
        "multimodal video understanding, Google Cloud Storage, and Firestore."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware (allows local Next.js frontend or edge camera nodes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for Cloud Run container liveness probes."""
    return {
        "status": "healthy",
        "service": "aisle-backend",
        "gcp_project": settings.GCP_PROJECT_ID,
        "gcs_bucket": settings.GCS_BUCKET_NAME,
        "model": settings.GEMINI_MODEL,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_service.main:app", host=settings.HOST, port=settings.PORT, reload=True)
