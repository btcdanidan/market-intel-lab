from app.signals.valuation import compute_valuation_gaps


def test_compute_valuation_gaps_returns_symbol_map() -> None:
    rows = [
        {
            "symbol": "BTC",
            "basis_score": 0.2,
            "positioning_score": 0.1,
            "options_score": -0.1,
            "orderbook_score": 0.4,
        },
        {
            "symbol": "ETH",
            "basis_score": -0.3,
            "positioning_score": -0.2,
            "options_score": 0.2,
            "orderbook_score": -0.1,
        },
    ]

    valuation = compute_valuation_gaps(rows)

    assert set(valuation.keys()) == {"BTC", "ETH"}
    assert valuation["BTC"] != valuation["ETH"]
