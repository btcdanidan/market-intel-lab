from datetime import UTC, datetime

from app.core.types import MarketSnapshot
from app.signals.features import compute_feature_vector


def test_compute_feature_vector_has_expected_keys() -> None:
    snapshot = MarketSnapshot(
        venue="composite",
        symbol="BTC",
        ts=datetime.now(UTC),
        spot_price=100.0,
        perp_price=101.0,
        funding_rate=0.0005,
        perp_open_interest=15000.0,
        bid=99.9,
        ask=100.1,
        bid_size=200.0,
        ask_size=180.0,
        options_put_oi=1200.0,
        options_call_oi=1500.0,
        options_skew_25d=2.1,
        implied_vol=55.0,
    )

    vector = compute_feature_vector(snapshot)

    assert vector["symbol"] == "BTC"
    assert -1.0 <= vector["orderbook_score"] <= 1.0
    assert -1.0 <= vector["positioning_score"] <= 1.0
    assert -1.0 <= vector["options_score"] <= 1.0
    assert -1.0 <= vector["basis_score"] <= 1.0
    assert vector["atr_proxy_pct"] >= 0.8
