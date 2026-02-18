from __future__ import annotations

from statistics import mean, pstdev

from app.signals.features import FeatureVector


def _zscore_map(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    mu = mean(values.values())
    sigma = pstdev(values.values())
    if sigma == 0:
        return {key: 0.0 for key in values}
    return {key: (value - mu) / sigma for key, value in values.items()}


def compute_valuation_gaps(feature_vectors: list[FeatureVector]) -> dict[str, float]:
    basis = {str(row["symbol"]): float(row["basis_score"]) for row in feature_vectors}
    positioning = {str(row["symbol"]): float(row["positioning_score"]) for row in feature_vectors}
    options = {str(row["symbol"]): float(row["options_score"]) for row in feature_vectors}
    orderbook = {str(row["symbol"]): float(row["orderbook_score"]) for row in feature_vectors}

    z_basis = _zscore_map(basis)
    z_positioning = _zscore_map(positioning)
    z_options = _zscore_map(options)
    z_orderbook = _zscore_map(orderbook)

    valuation: dict[str, float] = {}
    for symbol in basis:
        score = (
            -0.35 * z_basis[symbol]
            - 0.25 * z_positioning[symbol]
            - 0.20 * z_options[symbol]
            + 0.20 * z_orderbook[symbol]
        )
        valuation[symbol] = round(score, 6)
    return valuation
