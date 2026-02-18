from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.config.settings import Settings
from app.core.types import (
    AnalysisRequest,
    AnalysisResult,
    DailyMemo,
    DerivedSignals,
)
from app.ingestion.pipeline import IngestionPipeline
from app.memo.generator import MemoGenerator
from app.risk.engine import PortfolioContext, RiskEngine
from app.signals.features import FeatureVector, compute_feature_vector
from app.signals.regime import classify_regime
from app.signals.valuation import compute_valuation_gaps
from app.storage.repositories import AnalysisRepository


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        repository: AnalysisRepository,
        ingestion: IngestionPipeline,
        risk_engine: RiskEngine,
        memo_generator: MemoGenerator,
    ):
        self.settings = settings
        self.repository = repository
        self.ingestion = ingestion
        self.risk_engine = risk_engine
        self.memo_generator = memo_generator

    def run_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        assets = request.assets or self.settings.asset_universe
        run_id = uuid4().hex[:12]

        request_payload = request.model_dump(mode="json")
        self.repository.create_run(
            run_id=run_id, reason=request.reason, assets=assets, payload=request_payload
        )

        try:
            snapshots, data_issues, degraded = self.ingestion.ingest(assets)
            self.repository.store_snapshots(run_id, snapshots)

            feature_rows: list[FeatureVector] = [
                compute_feature_vector(snapshot) for snapshot in snapshots
            ]
            valuation_map = compute_valuation_gaps(feature_rows)
            regime, regime_confidence, regime_metrics = classify_regime(feature_rows)

            signals: list[DerivedSignals] = []
            for row in feature_rows:
                symbol = str(row["symbol"])
                confidence_raw = (
                    0.5 + abs(float(row["orderbook_score"])) * 0.25 + regime_confidence * 0.25
                )
                confidence = max(0.1, min(0.95, confidence_raw))
                if symbol not in {"BTC", "ETH"} and any(
                    gap.startswith(f"{symbol}:missing_options_data") for gap in data_issues
                ):
                    confidence = max(0.1, confidence - 0.15)

                signals.append(
                    DerivedSignals(
                        symbol=symbol,
                        orderbook_score=float(row["orderbook_score"]),
                        positioning_score=float(row["positioning_score"]),
                        options_score=float(row["options_score"]),
                        basis_score=float(row["basis_score"]),
                        valuation_gap_z=float(valuation_map[symbol]),
                        regime=regime,
                        confidence=round(confidence, 4),
                        components={
                            "spread_bps": float(row["spread_bps"]),
                            "depth_imbalance": float(row["depth_imbalance"]),
                            "slippage_bps": float(row["slippage_bps"]),
                            "basis_annualized": float(row["basis_annualized"]),
                            "put_call_ratio": float(row["put_call_ratio"]),
                            "atr_proxy_pct": float(row["atr_proxy_pct"]),
                            "regime_confidence": regime_confidence,
                        },
                    )
                )

            self.repository.store_signals(run_id, signals)

            spot_map = {
                snapshot.symbol: float(snapshot.spot_price or 0.0) for snapshot in snapshots
            }
            atr_map = {str(row["symbol"]): float(row["atr_proxy_pct"]) for row in feature_rows}

            equity = request.portfolio_equity or self.settings.portfolio_equity
            portfolio_ctx = PortfolioContext(equity=equity)
            trade_setups, risk_state = self.risk_engine.build_trade_setups(
                signals=signals,
                spot_prices=spot_map,
                atr_proxy_pct=atr_map,
                regime=regime,
                degraded=degraded,
                portfolio=portfolio_ctx,
                risk_pct_override=request.per_trade_risk_pct,
            )
            self.repository.store_trade_setups(run_id, trade_setups)

            facts = [
                f"Run timestamp: {datetime.now(UTC).isoformat()}",
                f"Universe: {', '.join(assets)}",
                f"Regime metrics: {regime_metrics}",
                f"Data quality issues count: {len(data_issues)}",
            ]
            assumptions = [
                "Public endpoints are representative despite potential exchange rate limits.",
                "Perp OI + funding are acceptable proxies for short-pressure in v1.",
                (
                    "Composite valuation score can be used as a directional input, "
                    "not a standalone trigger."
                ),
            ]
            inferences = [
                "Signal confidence rises when order-book and derivatives signals align.",
                "Missing options context on non-BTC/ETH assets should reduce conviction.",
                "Risk caps dominate position sizing regardless of conviction strength.",
            ]

            market_brief = {
                "key_macro_drivers": (
                    "Liquidity regime, derivatives carry, and volatility compression/expansion."
                ),
                "cross_asset_signals": "Breadth and funding dispersion across majors.",
                "risk_indicators": "Funding flips, spread widening, and OI spikes against trend.",
                "opportunities": ", ".join(
                    [f"{setup.direction} {setup.symbol}" for setup in trade_setups]
                )
                if trade_setups
                else "No-trade due to quality/risk constraints",
                "tail_risks": "Macro headline shock, exchange outage, and liquidity air pocket.",
            }

            scenarios = self.memo_generator.build_scenarios(regime)
            memo = DailyMemo(
                run_id=run_id,
                generated_at=datetime.now(UTC),
                regime=regime,
                market_brief=market_brief,
                trade_memos=trade_setups,
                scenarios=scenarios,
                bullish_counterargument=(
                    "Valuation dislocations can unwind quickly if liquidity improves "
                    "faster than expected."
                ),
                bearish_counterargument=(
                    "Crowded positioning can persist and trigger further downside "
                    "before mean reversion."
                ),
                facts=facts,
                assumptions=assumptions,
                inferences=inferences,
                data_gaps=data_issues,
                risk_state=risk_state,
            )
            memo_path, memo_body = self.memo_generator.write(memo)

            self.repository.mark_run_completed(
                run_id=run_id,
                regime=regime,
                degraded=degraded,
                quality={"issues": data_issues, "critical": degraded},
                memo_path=memo_path,
                memo_body=memo_body,
            )

            return AnalysisResult(
                run_id=run_id,
                status="completed",
                regime=regime,
                degraded=degraded,
                memo_path=memo_path,
                memo_body=memo_body,
                snapshots=snapshots,
                signals=signals,
                trade_setups=trade_setups,
                risk_state=risk_state,
                facts=facts,
                assumptions=assumptions,
                inferences=inferences,
                data_gaps=data_issues,
            )
        except Exception as exc:  # noqa: BLE001
            self.repository.mark_run_failed(run_id, str(exc))
            raise

    def get_run(self, run_id: str) -> dict | None:
        return self.repository.get_run(run_id)

    def get_latest_run(self) -> dict | None:
        return self.repository.get_latest_run()

    def list_runs(self, limit: int = 20) -> list[dict]:
        return self.repository.list_runs(limit)
