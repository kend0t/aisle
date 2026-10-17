import os

# Keep tests offline: environment variables take precedence over .env files, so a
# developer's live GCP config is never used and mock events never reach Firestore.
os.environ["GCP_PROJECT_ID"] = "mock-gcp-project"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/nonexistent/aisle-test-key.json"
os.environ["GEMINI_API_KEY"] = ""
