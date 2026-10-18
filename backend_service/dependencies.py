from dataclasses import dataclass

from fastapi import Request

from backend_service.config import Settings
from backend_service.db.firestore_client import EventRepository, build_repository
from backend_service.services.chat_service import StoreChatService
from backend_service.services.clip_media import ClipMediaService
from backend_service.services.gemini_analyzer import GeminiAnalyzerService
from backend_service.services.gemini_client import GeminiClient
from backend_service.services.insights_service import InsightsService
from backend_service.services.storage_service import StorageService


@dataclass(frozen=True)
class Services:
    repo: EventRepository
    storage: StorageService
    media: ClipMediaService
    analyzer: GeminiAnalyzerService
    chat: StoreChatService
    insights: InsightsService


def build_services(settings: Settings) -> Services:
    """Creates every service once, at startup. Raises DataSourceError when Firestore or
    Cloud Storage cannot be set up in firestore mode."""
    seed = settings.AISLE_DATA_SOURCE == "seed"
    repo = build_repository(settings)
    storage = StorageService(settings, use_gcs=not seed)
    gemini = GeminiClient(settings)
    chat = StoreChatService(repo, gemini)
    return Services(
        repo=repo,
        storage=storage,
        media=ClipMediaService(storage, allow_sample_clip=seed),
        analyzer=GeminiAnalyzerService(gemini, storage, settings.READS_PER_CLIP),
        chat=chat,
        insights=InsightsService(repo, chat, gemini),
    )


def _services(request: Request) -> Services:
    return request.app.state.services


def get_repo(request: Request) -> EventRepository:
    return _services(request).repo


def get_storage(request: Request) -> StorageService:
    return _services(request).storage


def get_media(request: Request) -> ClipMediaService:
    return _services(request).media


def get_analyzer(request: Request) -> GeminiAnalyzerService:
    return _services(request).analyzer


def get_chat(request: Request) -> StoreChatService:
    return _services(request).chat


def get_insights(request: Request) -> InsightsService:
    return _services(request).insights
