import os
from functools import lru_cache
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# GCP_PROJECT_ID value that means "no real project": Gemini runs in mock mode.
MOCK_PROJECT_ID = "mock-gcp-project"

# Ensure robust GRPC resolution on macOS
os.environ.setdefault("GRPC_DNS_RESOLVER", "native")
os.environ.setdefault("GRPC_POLL_STRATEGY", "poll")


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # GCP Core
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", MOCK_PROJECT_ID)
    GCP_REGION: str = os.getenv("GCP_REGION", "us-central1")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "aisle-interaction-clips")
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
    FIRESTORE_COLLECTION: str = os.getenv("FIRESTORE_COLLECTION", "interaction_events")

    # Where events and clips come from. "firestore" uses Firestore and Cloud Storage and
    # fails loudly when they fail. "seed" serves the bundled benchmark events from memory
    # and stores uploads on local disk, for offline work and tests.
    AISLE_DATA_SOURCE: Literal["firestore", "seed"] = "firestore"

    # Vertex AI / Gemini
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS", None
    )

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Edge / Mock upload directory for local processing
    LOCAL_UPLOAD_DIR: str = "temp_uploads"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend_service/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Returns cached application settings instance."""
    return Settings()
