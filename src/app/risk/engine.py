from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from app.config.settings import Settings
from app.core.types import DerivedSignals, RiskState, TradeSetup


@dataclass(slots=True)
class PortfolioContext:
    equity: float
    current_drawdown_pct: float = 0.0
    gross_exposure: float = 0.0


class RiskEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build_trade_setups(
        self,
        signals: list[DerivedSignals],
        spot_prices: dict[str, float],
        atr_proxy_pct: dict[str, float],
        regime: str,
        degraded: bool,
        portfolio: PortfolioContext,
        risk_pct_override: float | None = None,
    ) -> tuple[list[TradeSetup], RiskState]:
        notes: list[str] = []
        per_trade_risk_pct = risk_pct_override or self.settings.per_trade_risk_pct
        per_trade_risk_budget = portfolio.equity * (per_trade_risk_pct / 100)
        kill_switch = portfolio.current_drawdown_pct >= self.settings.drawdown_kill_switch_pct
        remaining_budget = max(
            0.0, portfolio.equity * self.settings.max_gross_exposure - portfolio.gross_exposure
        )

        if degraded:
            notes.append("No-trade mode: critical data quality gate failed.")
        if kill_switch:
            notes.append("Kill-switch active: portfolio drawdown threshold exceeded.")

        if degraded or kill_switch:
            return [], RiskState(
                gross_exposure=portfolio.gross_exposure,
                dd_pct=portfolio.current_drawdown_pct,
                kill_switch=kill_switch,
                per_trade_risk_budget=round(per_trade_risk_budget, 4),
                remaining_budget=round(remaining_budget, 4),
                notes=notes,
            )

        setups: list[TradeSetup] = []
        regime_horizon = 10 if regime == "risk-on" else 7 if regime == "transition" else 5

        sorted_candidates = sorted(
            signals, key=lambda item: abs(item.valuation_gap_z), reverse=True
        )
        for signal in sorted_candidates:
            symbol = signal.symbol
            if symbol not in spot_prices:
                continue
            entry = spot_prices[symbol]
            if entry <= 0:
                continue

            direction = (
                "Long"
                if signal.valuation_gap_z > 0.25
                else "Short"
                if signal.valuation_gap_z < -0.25
                else None
            )
            if direction is None:
                continue

            atr_pct = atr_proxy_pct.get(symbol, 2.0)
            structure_buffer_pct = 1.4
            stop_distance_pct = (
                structure_buffer_pct + self.settings.stop_atr_multiplier * atr_pct
            ) / 100
            stop_distance_abs = max(0.001, entry * stop_distance_pct)

            if direction == "Long":
                stop = entry - stop_distance_abs
                target1 = entry + stop_distance_abs * 1.8
                target2 = entry + stop_distance_abs * 2.5
                thesis = (
                    f"{symbol} screens undervalued versus composite derivatives "
                    "positioning with improving microstructure."
                )
                invalidation = (
                    "Order-book demand fails and spot closes below buffered structure stop."
                )
            else:
                stop = entry + stop_distance_abs
                target1 = entry - stop_distance_abs * 1.8
                target2 = entry - stop_distance_abs * 2.5
                thesis = (
                    f"{symbol} screens overvalued with crowded positioning and weak "
                    "microstructure support."
                )
                invalidation = (
                    "Bearish positioning unwind fails and spot reclaims buffered structure stop."
                )

            size_notional = per_trade_risk_budget / stop_distance_pct
            capped_size = min(size_notional, remaining_budget)
            if capped_size <= 0:
                notes.append("Gross exposure cap reached; skipped additional setups.")
                break

            remaining_budget -= capped_size
            portfolio.gross_exposure += capped_size

            typed_direction = cast(Literal["Long", "Short"], direction)
            confidence: Literal["Low", "Med", "High"] = (
                "High"
                if signal.confidence >= 0.75
                else "Med"
                if signal.confidence >= 0.5
                else "Low"
            )

            setup = TradeSetup(
                symbol=symbol,
                direction=typed_direction,
                horizon_days=regime_horizon,
                thesis=thesis,
                catalysts=[
                    "Funding and OI regime change",
                    "Options skew normalization",
                    "Liquidity depth improvement",
                ],
                entry_zone=f"{entry * 0.997:.4f} - {entry * 1.003:.4f}",
                stop=round(stop, 6),
                targets=[round(target1, 6), round(target2, 6)],
                reward_risk=round(
                    abs((target1 - entry) / (entry - stop))
                    if direction == "Long"
                    else abs((entry - target1) / (stop - entry)),
                    3,
                ),
                invalidation_trigger=invalidation,
                what_changes_my_mind=(
                    "Sustained adverse funding + opposite direction depth imbalance "
                    "for two sessions."
                ),
                size_notional=round(capped_size, 2),
                confidence=confidence,
            )
            setups.append(setup)

            if len(setups) >= 2:
                break

        risk_state = RiskState(
            gross_exposure=round(portfolio.gross_exposure, 2),
            dd_pct=round(portfolio.current_drawdown_pct, 3),
            kill_switch=kill_switch,
            per_trade_risk_budget=round(per_trade_risk_budget, 2),
            remaining_budget=round(max(remaining_budget, 0.0), 2),
            notes=notes,
        )
        return setups, risk_state
