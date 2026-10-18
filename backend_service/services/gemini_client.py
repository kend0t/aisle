import logging
import os
from typing import Any, List, Type, TypeVar

from pydantic import BaseModel

from backend_service.config import MOCK_PROJECT_ID, Settings
from backend_service.errors import GeminiError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """One google-genai client for the whole app.

    Vertex AI when a real GCP project is configured, otherwise a Gemini API key,
    otherwise unavailable, in which case callers use their mock behavior.
    """

    def __init__(self, settings: Settings) -> None:
        self.model = settings.GEMINI_MODEL
        self.mode = "unavailable"
        self._client = None

        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

        from google import genai

        if settings.GCP_PROJECT_ID and settings.GCP_PROJECT_ID != MOCK_PROJECT_ID:
            self._client = genai.Client(
                vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION
            )
            self.mode = "vertex"
        elif settings.GEMINI_API_KEY:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.mode = "api_key"

        logger.info("Gemini client: %s (model %s)", self.mode, self.model)

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate(self, *, system: str, contents: List[Any], schema: Type[T], temperature: float) -> T:
        """Runs one call whose JSON output Gemini must shape to `schema`."""
        if self._client is None:
            raise GeminiError("call (not configured)")

        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            if isinstance(response.parsed, schema):
                return response.parsed
            return schema.model_validate_json(response.text or "")
        except Exception as e:
            raise GeminiError("call", e) from e
