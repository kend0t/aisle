import os

import pytest
from fastapi.testclient import TestClient

# Keep tests offline: environment variables take precedence over .env files, so a
# developer's live GCP config is never used and test events never reach Firestore.
os.environ["AISLE_DATA_SOURCE"] = "seed"
os.environ["GCP_PROJECT_ID"] = "mock-gcp-project"
os.environ["GEMINI_API_KEY"] = ""


@pytest.fixture(scope="session")
def client():
    from backend_service.main import app

    # The context manager runs the app lifespan, which builds the services.
    with TestClient(app) as test_client:
        yield test_client
