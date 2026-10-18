from typing import Optional


class ServiceError(RuntimeError):
    """A backing service failed.

    The API answers with `status_code` and `public_detail`. The full cause is logged,
    never sent to the client.
    """

    status_code = 503

    def __init__(self, service: str, action: str, cause: Optional[BaseException] = None) -> None:
        self.service = service
        self.action = action
        self.cause = cause
        super().__init__(f"{service} {action} failed" + (f": {cause}" if cause else ""))

    @property
    def public_detail(self) -> str:
        reason = f" ({type(self.cause).__name__})" if self.cause else ""
        return f"{self.service} {self.action} failed{reason}"


class DataSourceError(ServiceError):
    """Firestore or Cloud Storage failed. There is no silent fallback to other data."""

    status_code = 503


class GeminiError(ServiceError):
    """A Gemini call failed or returned output that does not match the schema."""

    status_code = 502

    def __init__(self, action: str, cause: Optional[BaseException] = None) -> None:
        super().__init__("Gemini", action, cause)
