import logging
import os
from typing import Any, Callable, Dict, List, Tuple, Type, TypeVar

from pydantic import BaseModel

from backend_service.config import MOCK_PROJECT_ID, Settings
from backend_service.errors import GeminiError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Rounds of tool calls before Gemini must answer.
MAX_TOOL_ROUNDS = 4


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
            location = settings.GEMINI_LOCATION or settings.GCP_REGION
            # Vertex AI routing:
            # - gemini-3.8 family is deployed on the global endpoint
            # - Pro models are routed to us-central1 if regional location lacks quota/deployment
            if "3.8" in settings.GEMINI_MODEL.lower():
                location = "global"
            elif "pro" in settings.GEMINI_MODEL.lower() and location in ("asia-southeast1", "asia-east1"):
                location = "us-central1"
            self._client = genai.Client(
                vertexai=True, project=settings.GCP_PROJECT_ID, location=location
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

    def run_tools(
        self,
        *,
        system: str,
        contents: List[Any],
        tools: Dict[str, Callable[..., Dict[str, Any]]],
        temperature: float,
    ) -> Tuple[str, List[str]]:
        """Lets Gemini call `tools` until it answers. Returns the final text and a trace
        of the calls made, such as "count_outcomes(zone_id='left_bay_cereal')"."""
        if self._client is None:
            raise GeminiError("call (not configured)")

        from google.genai import types

        api = "VERTEX_AI" if self.mode == "vertex" else "GEMINI_API"
        declarations = [
            types.FunctionDeclaration.from_callable_with_api_option(callable=fn, api_option=api)
            for fn in tools.values()
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            tools=[types.Tool(function_declarations=declarations)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        history: List[Any] = list(contents)
        trace: List[str] = []

        try:
            for round_number in range(MAX_TOOL_ROUNDS + 1):
                if round_number == MAX_TOOL_ROUNDS:
                    # Out of rounds: answer from what the tools returned so far.
                    config = config.model_copy(update={"tool_config": types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(mode="NONE")
                    )})
                response = self._client.models.generate_content(
                    model=self.model, contents=history, config=config
                )
                calls = response.function_calls or []
                if not calls:
                    return response.text or "", trace

                history.append(response.candidates[0].content)
                results = []
                for call in calls:
                    args = dict(call.args or {})
                    trace.append(f"{call.name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
                    fn = tools.get(call.name or "")
                    try:
                        output = fn(**args) if fn else {"error": f"Unknown tool {call.name}"}
                    except Exception as e:  # A bad argument is reported back, not raised.
                        output = {"error": str(e)}
                    results.append(types.Part.from_function_response(name=call.name or "", response=output))
                history.append(types.Content(role="user", parts=results))
        except GeminiError:
            raise
        except Exception as e:
            raise GeminiError("call", e) from e
        return "", trace
