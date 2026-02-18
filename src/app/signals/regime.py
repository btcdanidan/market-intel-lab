from __future__ import annotations

from statistics import mean, pstdev

from app.core.types import RegimeState
from app.signals.features import FeatureVector


def classify_regime(
    feature_vectors: list[FeatureVector],
) -> tuple[RegimeState, float, dict[str, float]]:
    if not feature_vectors:
        return "transition", 0.1, {"breadth": 0.0, "volatility_proxy": 0.0, "funding_bias": 0.0}

    orderbook_scores = [float(row["orderbook_score"]) for row in feature_vectors]
    volatility_values = [float(row["atr_proxy_pct"]) for row in feature_vectors]
    funding_values = [float(row["funding_rate"]) for row in feature_vectors]

    breadth = mean(1.0 if score > 0 else 0.0 for score in orderbook_scores)
    volatility_proxy = mean(volatility_values)
    funding_bias = mean(funding_values)
    dispersion = pstdev(orderbook_scores) if len(feature_vectors) > 1 else 0.0

    if breadth >= 0.6 and funding_bias >= -0.0005 and volatility_proxy < 4.0:
        regime: RegimeState = "risk-on"
    elif breadth <= 0.4 and (funding_bias < -0.0005 or volatility_proxy >= 4.5):
        regime = "risk-off"
    else:
        regime = "transition"

    confidence = 0.45 + abs(breadth - 0.5) + min(0.2, abs(funding_bias) * 50)
    confidence -= min(0.2, dispersion / 2)
    confidence = max(0.1, min(0.95, confidence))

    metrics = {
        "breadth": round(breadth, 6),
        "volatility_proxy": round(volatility_proxy, 6),
        "funding_bias": round(funding_bias, 8),
        "dispersion": round(dispersion, 6),
    }
    return regime, round(confidence, 6), metrics
