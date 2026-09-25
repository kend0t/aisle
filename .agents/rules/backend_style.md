# Backend Coding Patterns & Style Guide

These rules govern the development of the Python backend services (Cloud Run / Cloud Functions) interacting with Vertex AI and Firestore.

## 1. Technology Stack & Language
- **Language:** Python 3.10+
- **Framework:** FastAPI (recommended for its speed and auto-generated Swagger documentation, which is great for hackathon demos) or lightweight Flask.
- **Type Hinting:** PEP 484 type hints are **mandatory** for all function arguments and return types.

## 2. Architecture & Modularity
- **Separation of Concerns:** Do not put all logic in `main.py`. Separate files by domain:
  - `api/` (Routing and endpoint definitions)
  - `services/` (Business logic, e.g., calling Vertex AI)
  - `db/` (Firestore interactions)
  - `models/` (Data validation schemas)

## 3. Data Validation (Crucial for Gen AI)
- Use **Pydantic** to define the expected structure of the JSON returned by Gemini 1.5 Pro.
- LLM outputs can occasionally be unpredictable; you must validate the output against your Pydantic schema before attempting to write it to Firestore. 
- Gracefully handle schema validation errors (e.g., if Gemini returns invalid JSON, retry the prompt or log a specific error).

## 4. Error Handling & Logging
- Wrap all external API calls (Vertex AI, Google Cloud Storage, Firestore) in `try/except` blocks.
- Use Python's built-in `logging` module. Do not just `print()`. Log meaningful context: `"Failed to parse Gemini response for video {video_id}"`.

## 5. Environment & Configuration
- Never hardcode credentials, bucket names, or project IDs.
- Use environment variables (via `os.getenv` or a `.env` file locally). This is critical for seamless deployment to Cloud Run.
