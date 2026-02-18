from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Any

from app.config.settings import Settings


@dataclass(slots=True)
class ExchangeSnapshot:
    venue: str
    symbol: str
    ts: datetime
    spot_mid: float | None
    perp_mid: float | None
    funding_rate: float | None
    perp_open_interest: float | None
    bid: float | None
    ask: float | None
    bid_size: float | None
    ask_size: float | None
    issues: list[str]
    raw: dict[str, Any]


class CCXTClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._clients: dict[str, Any] = {}

    def _get_client(self, exchange_name: str) -> Any:
        if exchange_name in self._clients:
            return self._clients[exchange_name]

        import ccxt  # Local import so tests can stub this module without installing deps.

        exchange_class = getattr(ccxt, exchange_name)
        params: dict[str, Any] = {"enableRateLimit": True}

        if exchange_name == "binance":
            params["apiKey"] = self.settings.binance_api_key
            params["secret"] = self.settings.binance_api_secret
        elif exchange_name == "coinbase":
            params["apiKey"] = self.settings.coinbase_api_key
            params["secret"] = self.settings.coinbase_api_secret

        client = exchange_class(params)
        self._clients[exchange_name] = client
        return client

    @staticmethod
    def _spot_symbol(asset: str, exchange_name: str) -> str:
        return f"{asset}/USD" if exchange_name == "coinbase" else f"{asset}/USDT"

    @staticmethod
    def _perp_symbol(asset: str, exchange_name: str) -> str | None:
        if exchange_name == "binance":
            return f"{asset}/USDT:USDT"
        return None

    def fetch_asset_snapshot(self, exchange_name: str, asset: str) -> ExchangeSnapshot:
        client = self._get_client(exchange_name)
        now = datetime.now(UTC)
        symbol = asset.upper()
        issues: list[str] = []
        raw: dict[str, Any] = {}

        spot_mid = None
        perp_mid = None
        funding_rate = None
        perp_open_interest = None
        bid = None
        ask = None
        bid_size = None
        ask_size = None

        spot_symbol = self._spot_symbol(symbol, exchange_name)
        try:
            ticker = client.fetch_ticker(spot_symbol)
            order_book = client.fetch_order_book(spot_symbol, limit=25)
            spot_mid = self._mid_from_orderbook(order_book)
            bid, ask, bid_size, ask_size = self._level1(order_book)
            raw["spot_ticker"] = ticker
            raw["spot_order_book"] = {
                "bids": order_book.get("bids", [])[:5],
                "asks": order_book.get("asks", [])[:5],
            }
        except Exception as exc:  # noqa: BLE001
            issues.append(f"{exchange_name}:{symbol}:spot_fetch_failed:{exc}")

        perp_symbol = self._perp_symbol(symbol, exchange_name)
        if perp_symbol:
            try:
                perp_ticker = client.fetch_ticker(perp_symbol)
                perp_order_book = client.fetch_order_book(perp_symbol, limit=25)
                perp_mid = self._mid_from_orderbook(perp_order_book)
                funding = client.fetch_funding_rate(perp_symbol)
                funding_rate = float(funding.get("fundingRate") or 0.0)
                oi = client.fetch_open_interest(perp_symbol)
                perp_open_interest = float(
                    oi.get("openInterestAmount") or oi.get("openInterestValue") or 0.0
                )
                raw["perp_ticker"] = perp_ticker
                raw["perp_order_book"] = {
                    "bids": perp_order_book.get("bids", [])[:5],
                    "asks": perp_order_book.get("asks", [])[:5],
                }
                raw["perp_funding"] = funding
                raw["perp_open_interest"] = oi
            except Exception as exc:  # noqa: BLE001
                issues.append(f"{exchange_name}:{symbol}:perp_fetch_failed:{exc}")
        else:
            issues.append(f"{exchange_name}:{symbol}:perp_not_supported")

        return ExchangeSnapshot(
            venue=exchange_name,
            symbol=symbol,
            ts=now,
            spot_mid=spot_mid,
            perp_mid=perp_mid,
            funding_rate=funding_rate,
            perp_open_interest=perp_open_interest,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            issues=issues,
            raw=raw,
        )

    @staticmethod
    def _mid_from_orderbook(order_book: dict[str, Any]) -> float | None:
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if not bids or not asks:
            return None
        return (float(bids[0][0]) + float(asks[0][0])) / 2

    @staticmethod
    def _level1(
        order_book: dict[str, Any],
    ) -> tuple[float | None, float | None, float | None, float | None]:
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if not bids or not asks:
            return None, None, None, None
        return float(bids[0][0]), float(asks[0][0]), float(bids[0][1]), float(asks[0][1])

    @staticmethod
    def median_or_none(values: list[float | None]) -> float | None:
        clean = [float(v) for v in values if v is not None]
        if not clean:
            return None
        return float(median(clean))
