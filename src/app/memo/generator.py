from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.types import DailyMemo, ScenarioCase


class MemoGenerator:
    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def build_scenarios(self, regime: str) -> list[ScenarioCase]:
        if regime == "risk-on":
            return [
                ScenarioCase(
                    name="base",
                    probability=55,
                    description="Constructive tape with stable carry.",
                    expected_path="Grind higher with pullback buy opportunities.",
                ),
                ScenarioCase(
                    name="bullish",
                    probability=30,
                    description="Short-covering extension and vol compression.",
                    expected_path="Fast upside extension and skew normalization.",
                ),
                ScenarioCase(
                    name="bearish",
                    probability=15,
                    description="Event-driven risk-off shock.",
                    expected_path="Gap down then defensive mean reversion.",
                ),
            ]
        if regime == "risk-off":
            return [
                ScenarioCase(
                    name="base",
                    probability=50,
                    description="Defensive regime with fragile liquidity.",
                    expected_path="Choppy downside with episodic squeezes.",
                ),
                ScenarioCase(
                    name="bullish",
                    probability=20,
                    description="Positioning reset sparks rebound.",
                    expected_path="Sharp squeeze, then consolidation.",
                ),
                ScenarioCase(
                    name="bearish",
                    probability=30,
                    description="Continuation deleveraging.",
                    expected_path="Lower lows with rising realized vol.",
                ),
            ]
        return [
            ScenarioCase(
                name="base",
                probability=55,
                description="Mixed regime with selective opportunities.",
                expected_path="Range trading around valuation anchors.",
            ),
            ScenarioCase(
                name="bullish",
                probability=25,
                description="Breadth and funding improve together.",
                expected_path="Orderly trend-up with better depth.",
            ),
            ScenarioCase(
                name="bearish",
                probability=20,
                description="Macro headline volatility resurfaces.",
                expected_path="Range breakdown and downside skew expansion.",
            ),
        ]

    def render_markdown(self, memo: DailyMemo) -> str:
        lines: list[str] = []
        lines.append("## Market Brief")
        lines.append(f"- Regime classification: {memo.regime}")
        lines.append(f"- Key macro drivers: {memo.market_brief['key_macro_drivers']}")
        lines.append(f"- Cross-asset signals: {memo.market_brief['cross_asset_signals']}")
        lines.append(f"- Risk indicators to watch: {memo.market_brief['risk_indicators']}")
        lines.append(f"- Highest-conviction opportunities: {memo.market_brief['opportunities']}")
        lines.append(f"- Main tail risks: {memo.market_brief['tail_risks']}")
        lines.append("")

        lines.append("## Trade Memo")
        if not memo.trade_memos:
            lines.append("- Instrument: None")
            lines.append("- Direction: None")
            lines.append("- Horizon: N/A")
            lines.append("- Regime view: No-trade mode")
            lines.append(
                "- Thesis (1 sentence): Data quality or risk guardrails blocked execution."
            )
            lines.append("- Catalysts: Fresh data and regime confirmation")
            lines.append("- Entry zone: N/A")
            lines.append("- Stop: N/A")
            lines.append("- Target(s): N/A")
            lines.append("- Estimated reward:risk: N/A")
            lines.append("- Position size method: Risk budget formula inactive in no-trade mode")
            lines.append("- Confidence (Low/Med/High): Low")
            lines.append("- Invalidation trigger: Quality gate cleared")
            lines.append("- What changes my mind: Data freshness and signal confirmation")
        else:
            for setup in memo.trade_memos:
                lines.append(f"- Instrument: {setup.symbol}")
                lines.append(f"- Direction: {setup.direction}")
                lines.append(f"- Horizon: {setup.horizon_days} days")
                lines.append(f"- Regime view: {memo.regime}")
                lines.append(f"- Thesis (1 sentence): {setup.thesis}")
                lines.append(f"- Catalysts: {', '.join(setup.catalysts)}")
                lines.append(f"- Entry zone: {setup.entry_zone}")
                lines.append(f"- Stop: {setup.stop}")
                lines.append(f"- Target(s): {', '.join(str(t) for t in setup.targets)}")
                lines.append(f"- Estimated reward:risk: {setup.reward_risk}")
                lines.append("- Position size method: position_size = risk_budget / stop_distance")
                lines.append(f"- Confidence (Low/Med/High): {setup.confidence}")
                lines.append(f"- Invalidation trigger: {setup.invalidation_trigger}")
                lines.append(f"- What changes my mind: {setup.what_changes_my_mind}")
                lines.append("")

        lines.append("## Scenario Analysis")
        for scenario in memo.scenarios:
            lines.append(
                f"- {scenario.name.capitalize()} ({scenario.probability}%): "
                f"{scenario.description} Expected path: {scenario.expected_path}"
            )
        lines.append("")

        lines.append("## Counterarguments")
        lines.append(f"- Bullish: {memo.bullish_counterargument}")
        lines.append(f"- Bearish: {memo.bearish_counterargument}")
        lines.append("")

        lines.append("## Risk Controls")
        lines.append(f"- Gross exposure: {memo.risk_state.gross_exposure}")
        lines.append(f"- Drawdown (%): {memo.risk_state.dd_pct}")
        lines.append(f"- Kill-switch: {memo.risk_state.kill_switch}")
        lines.append(f"- Per-trade risk budget: {memo.risk_state.per_trade_risk_budget}")
        lines.append(f"- Remaining risk capacity: {memo.risk_state.remaining_budget}")
        if memo.risk_state.notes:
            lines.append(f"- Notes: {'; '.join(memo.risk_state.notes)}")
        lines.append("")

        lines.append("## Facts")
        lines.extend([f"- {item}" for item in memo.facts])
        lines.append("")

        lines.append("## Assumptions")
        lines.extend([f"- {item}" for item in memo.assumptions])
        lines.append("")

        lines.append("## Inferences")
        lines.extend([f"- {item}" for item in memo.inferences])
        lines.append("")

        lines.append("## Data Gaps")
        lines.extend([f"- {item}" for item in memo.data_gaps] if memo.data_gaps else ["- None"])
        lines.append("")

        return "\n".join(lines)

    def write(self, memo: DailyMemo) -> tuple[str, str]:
        markdown = self.render_markdown(memo)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{stamp}_{memo.run_id}.md"
        path = self.reports_dir / filename
        path.write_text(markdown, encoding="utf-8")
        return str(path), markdown
