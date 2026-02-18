from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.config.settings import Settings
from app.connectors.ccxt_client import CCXTClient
from app.connectors.deribit_client import DeribitClient
from app.core.types import MarketSnapshot


class IngestionPipeline:
    def __init__(self, settings: Settings, ccxt_client: CCXTClient, deribit_client: DeribitClient):
        self.settings = settings
        self.ccxt_client = ccxt_client
        self.deribit_client = deribit_client

    def ingest(self, assets: list[str]) -> tuple[list[MarketSnapshot], list[str], bool]:
        snapshots: list[MarketSnapshot] = []
        issues: list[str] = []

        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(minutes=self.settings.data_stale_minutes)

        for asset in assets:
            venue_rows: list[Any] = []
            for venue in self.settings.exchanges:
                try:
                    row = self.ccxt_client.fetch_asset_snapshot(venue, asset)
                    venue_rows.append(row)
                    issues.extend(row.issues)
                except Exception as exc:  # noqa: BLE001
                    issues.append(f"{venue}:{asset}:client_error:{exc}")

            deribit = self.deribit_client.fetch_option_metrics(asset)
            issues.extend(deribit.issues)

            spot_values = [row.spot_mid for row in venue_rows]
            perp_values = [row.perp_mid for row in venue_rows]
            funding_values = [row.funding_rate for row in venue_rows]
            oi_values = [row.perp_open_interest for row in venue_rows]
            bid_values = [row.bid for row in venue_rows]
            ask_values = [row.ask for row in venue_rows]
            bid_size_values = [row.bid_size for row in venue_rows]
            ask_size_values = [row.ask_size for row in venue_rows]

            ts_candidates = [row.ts for row in venue_rows] + [deribit.ts]
            latest_ts = max(ts_candidates) if ts_candidates else now
            quality_flags: list[str] = []

            if latest_ts < stale_cutoff:
                quality_flags.append(f"{asset}:stale_data")

            if not any(value is not None for value in spot_values):
                quality_flags.append(f"{asset}:missing_spot_data")
            if not any(value is not None for value in perp_values):
                quality_flags.append(f"{asset}:missing_perp_data")

            options_missing = deribit.put_oi is None or deribit.call_oi is None
            if options_missing:
                quality_flags.append(f"{asset}:missing_options_data")

            issues.extend(quality_flags)

            snapshot = MarketSnapshot(
                venue="composite",
                symbol=asset,
                ts=latest_ts,
                spot_price=self._median_or_none(spot_values),
                perp_price=self._median_or_none(perp_values),
                funding_rate=self._mean_or_none(funding_values),
                perp_open_interest=self._sum_or_none(oi_values),
                bid=self._median_or_none(bid_values),
                ask=self._median_or_none(ask_values),
                bid_size=self._sum_or_none(bid_size_values),
                ask_size=self._sum_or_none(ask_size_values),
                options_put_oi=deribit.put_oi,
                options_call_oi=deribit.call_oi,
                options_skew_25d=deribit.skew_25d,
                implied_vol=deribit.implied_vol,
                data_quality=quality_flags,
                raw={
                    "venues": [row.raw for row in venue_rows],
                    "options": deribit.raw,
                },
            )
            snapshots.append(snapshot)

        critical = any(
            "stale_data" in issue or "missing_spot_data" in issue or "missing_perp_data" in issue
            for issue in issues
        )
        return snapshots, sorted(set(issues)), critical

    @staticmethod
    def _median_or_none(values: list[float | None]) -> float | None:
        clean = sorted(float(value) for value in values if value is not None)
        if not clean:
            return None
        mid = len(clean) // 2
        if len(clean) % 2 == 1:
            return clean[mid]
        return (clean[mid - 1] + clean[mid]) / 2

    @staticmethod
    def _sum_or_none(values: list[float | None]) -> float | None:
        clean = [float(value) for value in values if value is not None]
        if not clean:
            return None
        return float(sum(clean))

    @staticmethod
    def _mean_or_none(values: list[float | None]) -> float | None:
        clean = [float(value) for value in values if value is not None]
        if not clean:
            return None
        return float(sum(clean) / len(clean))
