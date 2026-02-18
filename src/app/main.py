from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from redis import Redis

from app.api.routes_analysis import router as analysis_router
from app.api.routes_chat import router as chat_router
from app.api.routes_ui import router as ui_router
from app.chat.openai_client import OpenAIChatClient
from app.chat.service import ChatService
from app.config.settings import get_settings
from app.connectors.ccxt_client import CCXTClient
from app.connectors.deribit_client import DeribitClient
from app.core.service import AnalysisService
from app.ingestion.pipeline import IngestionPipeline
from app.memo.generator import MemoGenerator
from app.risk.engine import RiskEngine
from app.scheduler.jobs import AnalysisScheduler
from app.storage.repositories import AnalysisRepository


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)

    repository = AnalysisRepository(settings.database_url)
    repository.init_db()

    ccxt_client = CCXTClient(settings)
    deribit_client = DeribitClient()
    ingestion = IngestionPipeline(settings, ccxt_client, deribit_client)
    risk_engine = RiskEngine(settings)
    memo_generator = MemoGenerator(settings.reports_path)
    analysis_service = AnalysisService(
        settings=settings,
        repository=repository,
        ingestion=ingestion,
        risk_engine=risk_engine,
        memo_generator=memo_generator,
    )
    chat_service = ChatService(
        settings=settings,
        repository=repository,
        openai_client=OpenAIChatClient(api_key=settings.openai_api_key),
    )

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    scheduler = AnalysisScheduler(settings, analysis_service, redis_client)

    app.state.settings = settings
    app.state.repository = repository
    app.state.redis = redis_client
    app.state.deribit_client = deribit_client
    app.state.analysis_service = analysis_service
    app.state.chat_service = chat_service
    app.state.scheduler = scheduler

    ui_dir = Path(__file__).resolve().parent / "ui"
    app.mount("/ui", StaticFiles(directory=ui_dir), name="ui")
    app.include_router(ui_router)
    app.include_router(analysis_router)
    app.include_router(chat_router)

    @app.get("/health")
    def health() -> dict:
        redis_ok = True
        db_ok = True
        try:
            app.state.redis.ping()
        except Exception:  # noqa: BLE001
            redis_ok = False
        try:
            app.state.repository.init_db()
        except Exception:  # noqa: BLE001
            db_ok = False

        status = "ok" if redis_ok and db_ok else "degraded"
        return {"status": status, "redis": redis_ok, "database": db_ok}

    @app.on_event("startup")
    def on_startup() -> None:
        app.state.scheduler.start()

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        app.state.scheduler.shutdown()
        app.state.deribit_client.close()
        app.state.redis.close()

    return app


app = create_app()
