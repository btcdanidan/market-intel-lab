from datetime import UTC, datetime, timedelta

from app.config.settings import Settings
from app.connectors.ccxt_client import ExchangeSnapshot
from app.connectors.deribit_client import DeribitOptionMetrics
from app.ingestion.pipeline import IngestionPipeline


class StubCCXTClient:
    def __init__(self, stale: bool = False):
        self.stale = stale

    def fetch_asset_snapshot(self, exchange_name: str, asset: str) -> ExchangeSnapshot:
        ts = datetime.now(UTC)
        if self.stale:
            ts = ts - timedelta(hours=2)

        return ExchangeSnapshot(
            venue=exchange_name,
            symbol=asset,
            ts=ts,
            spot_mid=100.0,
            perp_mid=100.2,
            funding_rate=0.0001,
            perp_open_interest=10000.0,
            bid=99.9,
            ask=100.1,
            bid_size=100.0,
            ask_size=95.0,
            issues=[],
            raw={},
        )


class StubDeribitClient:
    def __init__(self, stale: bool = False):
        self.stale = stale

    def fetch_option_metrics(self, asset: str) -> DeribitOptionMetrics:
        ts = datetime.now(UTC)
        if self.stale:
            ts = ts - timedelta(hours=2)
        return DeribitOptionMetrics(
            symbol=asset,
            ts=ts,
            put_oi=500.0,
            call_oi=600.0,
            skew_25d=1.5,
            implied_vol=45.0,
            issues=[],
            raw={},
        )


def test_ingestion_pipeline_healthy_data_not_critical() -> None:
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        DATA_STALE_MINUTES=15,
        EXCHANGES="binance,coinbase",
    )
    pipeline = IngestionPipeline(
        settings=settings,
        ccxt_client=StubCCXTClient(stale=False),
        deribit_client=StubDeribitClient(),
    )

    snapshots, issues, critical = pipeline.ingest(["BTC"])

    assert len(snapshots) == 1
    assert critical is False
    assert all("stale_data" not in issue for issue in issues)


def test_ingestion_pipeline_stale_data_is_critical() -> None:
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        DATA_STALE_MINUTES=15,
        EXCHANGES="binance,coinbase",
    )
    pipeline = IngestionPipeline(
        settings=settings,
        ccxt_client=StubCCXTClient(stale=True),
        deribit_client=StubDeribitClient(stale=True),
    )

    snapshots, issues, critical = pipeline.ingest(["BTC"])

    assert len(snapshots) == 1
    assert critical is True
    assert any("stale_data" in issue for issue in issues)


def test_ingestion_pipeline_flags_missing_perp_as_critical() -> None:
    class MissingPerpClient(StubCCXTClient):
        def fetch_asset_snapshot(self, exchange_name: str, asset: str) -> ExchangeSnapshot:
            row = super().fetch_asset_snapshot(exchange_name, asset)
            row.perp_mid = None
            return row

    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        EXCHANGES="binance,coinbase",
    )
    pipeline = IngestionPipeline(
        settings=settings,
        ccxt_client=MissingPerpClient(),
        deribit_client=StubDeribitClient(),
    )

    snapshots, issues, critical = pipeline.ingest(["BTC"])

    assert len(snapshots) == 1
    assert critical is True
    assert any("missing_perp_data" in issue for issue in issues)
