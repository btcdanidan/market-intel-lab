from datetime import UTC, datetime

from app.config.settings import Settings
from app.connectors.ccxt_client import ExchangeSnapshot
from app.connectors.deribit_client import DeribitOptionMetrics
from app.core.service import AnalysisService
from app.core.types import AnalysisRequest
from app.ingestion.pipeline import IngestionPipeline
from app.memo.generator import MemoGenerator
from app.risk.engine import RiskEngine
from app.storage.repositories import AnalysisRepository


class FakeCCXTClient:
    def fetch_asset_snapshot(self, exchange_name: str, asset: str) -> ExchangeSnapshot:
        price = {
            "BTC": 100000.0,
            "ETH": 5000.0,
            "SOL": 180.0,
            "BNB": 700.0,
            "XRP": 1.0,
        }[asset]
        return ExchangeSnapshot(
            venue=exchange_name,
            symbol=asset,
            ts=datetime.now(UTC),
            spot_mid=price,
            perp_mid=price * 1.002,
            funding_rate=0.0002,
            perp_open_interest=10000.0,
            bid=price * 0.999,
            ask=price * 1.001,
            bid_size=120.0,
            ask_size=110.0,
            issues=[],
            raw={},
        )


class FakeDeribitClient:
    def fetch_option_metrics(self, asset: str) -> DeribitOptionMetrics:
        return DeribitOptionMetrics(
            symbol=asset,
            ts=datetime.now(UTC),
            put_oi=800.0,
            call_oi=1000.0,
            skew_25d=1.0,
            implied_vol=40.0,
            issues=[],
            raw={},
        )


def test_analysis_service_full_run(tmp_path) -> None:
    reports_path = tmp_path / "reports"
    settings = Settings(
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'app.db'}",
        REPORTS_DIR=str(reports_path),
        EXCHANGES="binance,coinbase",
        ASSET_UNIVERSE="BTC,ETH,SOL,BNB,XRP",
    )

    repository = AnalysisRepository(settings.database_url)
    repository.init_db()

    ingestion = IngestionPipeline(
        settings=settings,
        ccxt_client=FakeCCXTClient(),
        deribit_client=FakeDeribitClient(),
    )
    service = AnalysisService(
        settings=settings,
        repository=repository,
        ingestion=ingestion,
        risk_engine=RiskEngine(settings),
        memo_generator=MemoGenerator(reports_path),
    )

    result = service.run_analysis(AnalysisRequest(reason="manual"))

    assert result.status == "completed"
    assert result.regime in {"risk-on", "risk-off", "transition"}
    assert result.memo_path.endswith(".md")
    assert len(result.snapshots) == 5

    latest = service.get_latest_run()
    assert latest is not None
    assert latest["id"] == result.run_id
    assert latest["status"] == "completed"
