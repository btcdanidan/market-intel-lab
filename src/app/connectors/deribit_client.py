from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean
from typing import Any

import httpx


@dataclass(slots=True)
class DeribitOptionMetrics:
    symbol: str
    ts: datetime
    put_oi: float | None
    call_oi: float | None
    skew_25d: float | None
    implied_vol: float | None
    issues: list[str]
    raw: dict[str, Any]


class DeribitClient:
    def __init__(self, timeout: float = 10.0):
        self.base_url = "https://www.deribit.com/api/v2"
        self.client = httpx.Client(timeout=timeout)

    def fetch_option_metrics(self, asset: str) -> DeribitOptionMetrics:
        symbol = asset.upper()
        now = datetime.now(UTC)
        issues: list[str] = []
        raw: dict[str, Any] = {}

        if symbol not in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
            return DeribitOptionMetrics(
                symbol=symbol,
                ts=now,
                put_oi=None,
                call_oi=None,
                skew_25d=None,
                implied_vol=None,
                issues=[f"deribit:{symbol}:unsupported_asset"],
                raw={},
            )

        try:
            params = {"currency": symbol, "kind": "option"}
            response = self.client.get(
                f"{self.base_url}/public/get_book_summary_by_currency", params=params
            )
            response.raise_for_status()
            payload = response.json()
            books = payload.get("result", [])
            raw["book_summary"] = books
        except Exception as exc:  # noqa: BLE001
            return DeribitOptionMetrics(
                symbol=symbol,
                ts=now,
                put_oi=None,
                call_oi=None,
                skew_25d=None,
                implied_vol=None,
                issues=[f"deribit:{symbol}:fetch_failed:{exc}"],
                raw=raw,
            )

        put_oi = 0.0
        call_oi = 0.0
        put_iv: list[float] = []
        call_iv: list[float] = []

        for book in books:
            instrument_name = str(book.get("instrument_name", ""))
            open_interest = float(book.get("open_interest") or 0.0)
            iv = float(book.get("mark_iv") or 0.0)
            if instrument_name.endswith("-P"):
                put_oi += open_interest
                if iv > 0:
                    put_iv.append(iv)
            elif instrument_name.endswith("-C"):
                call_oi += open_interest
                if iv > 0:
                    call_iv.append(iv)

        put_oi_val: float | None = put_oi if put_oi > 0 else None
        call_oi_val: float | None = call_oi if call_oi > 0 else None

        if put_iv and call_iv:
            skew_25d = mean(put_iv) - mean(call_iv)
            implied_vol = mean(put_iv + call_iv)
        else:
            skew_25d = None
            implied_vol = None
            issues.append(f"deribit:{symbol}:missing_iv_surface")

        return DeribitOptionMetrics(
            symbol=symbol,
            ts=now,
            put_oi=put_oi_val,
            call_oi=call_oi_val,
            skew_25d=skew_25d,
            implied_vol=implied_vol,
            issues=issues,
            raw=raw,
        )

    def close(self) -> None:
        self.client.close()
