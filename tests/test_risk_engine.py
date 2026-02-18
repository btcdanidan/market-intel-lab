from app.config.settings import Settings
from app.core.types import DerivedSignals
from app.risk.engine import PortfolioContext, RiskEngine


def test_risk_engine_builds_setups_when_not_degraded() -> None:
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        REPORTS_DIR="reports",
        EXCHANGES="binance,coinbase",
    )
    engine = RiskEngine(settings)

    signals = [
        DerivedSignals(
            symbol="BTC",
            orderbook_score=0.6,
            positioning_score=-0.3,
            options_score=-0.1,
            basis_score=-0.2,
            valuation_gap_z=0.8,
            regime="risk-on",
            confidence=0.82,
            components={},
        )
    ]

    setups, risk = engine.build_trade_setups(
        signals=signals,
        spot_prices={"BTC": 100000.0},
        atr_proxy_pct={"BTC": 2.5},
        regime="risk-on",
        degraded=False,
        portfolio=PortfolioContext(equity=100000.0),
    )

    assert len(setups) == 1
    assert setups[0].direction == "Long"
    assert setups[0].size_notional > 0
    assert risk.kill_switch is False


def test_risk_engine_no_trade_when_degraded() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")
    engine = RiskEngine(settings)

    setups, risk = engine.build_trade_setups(
        signals=[],
        spot_prices={},
        atr_proxy_pct={},
        regime="transition",
        degraded=True,
        portfolio=PortfolioContext(equity=100000.0),
    )

    assert setups == []
    assert any("No-trade mode" in note for note in risk.notes)
