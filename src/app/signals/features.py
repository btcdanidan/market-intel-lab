from __future__ import annotations

import math

from app.core.types import MarketSnapshot

FeatureVector = dict[str, float | str]


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def compute_feature_vector(snapshot: MarketSnapshot) -> FeatureVector:
    spot = snapshot.spot_price or 0.0
    perp = snapshot.perp_price or spot
    bid = snapshot.bid or 0.0
    ask = snapshot.ask or 0.0
    bid_size = snapshot.bid_size or 0.0
    ask_size = snapshot.ask_size or 0.0
    funding = snapshot.funding_rate or 0.0
    oi = snapshot.perp_open_interest or 0.0
    put_oi = snapshot.options_put_oi or 0.0
    call_oi = snapshot.options_call_oi or 0.0
    skew = snapshot.options_skew_25d or 0.0

    spread_bps = ((ask - bid) / spot * 10_000) if spot and ask > bid else 25.0
    depth_imbalance = (bid_size - ask_size) / (bid_size + ask_size + 1e-9)
    slippage_bps = (1 / (bid_size + ask_size + 1.0)) * 10_000
    basis_annualized = ((perp - spot) / spot * 365) if spot else 0.0
    put_call_ratio = put_oi / (call_oi + 1e-9)

    orderbook_score = clamp(
        (depth_imbalance * 0.7) - (spread_bps / 1000) - (slippage_bps / 1000), -1.0, 1.0
    )
    positioning_score = clamp((funding * 20) - math.log1p(abs(oi)) / 20, -1.0, 1.0)
    options_score = clamp((1 - put_call_ratio) * 0.6 - skew / 100, -1.0, 1.0)
    basis_score = clamp(basis_annualized / 50, -1.0, 1.0)

    atr_proxy_pct = clamp((abs(perp - spot) / (spot + 1e-9)) * 100 + spread_bps / 200, 0.8, 8.0)

    return {
        "symbol": snapshot.symbol,
        "orderbook_score": round(orderbook_score, 6),
        "positioning_score": round(positioning_score, 6),
        "options_score": round(options_score, 6),
        "basis_score": round(basis_score, 6),
        "spread_bps": round(spread_bps, 6),
        "depth_imbalance": round(depth_imbalance, 6),
        "slippage_bps": round(slippage_bps, 6),
        "basis_annualized": round(basis_annualized, 6),
        "put_call_ratio": round(put_call_ratio, 6),
        "atr_proxy_pct": round(atr_proxy_pct, 6),
        "funding_rate": funding,
    }
