from datetime import UTC, datetime

from app.core.types import DailyMemo, RiskState, ScenarioCase
from app.memo.generator import MemoGenerator


def test_memo_generator_renders_required_sections(tmp_path) -> None:
    generator = MemoGenerator(tmp_path)
    memo = DailyMemo(
        run_id="abc123",
        generated_at=datetime.now(UTC),
        regime="transition",
        market_brief={
            "key_macro_drivers": "driver",
            "cross_asset_signals": "signals",
            "risk_indicators": "risk",
            "opportunities": "Long BTC",
            "tail_risks": "tail",
        },
        trade_memos=[],
        scenarios=[
            ScenarioCase(name="base", probability=55, description="base", expected_path="flat"),
            ScenarioCase(name="bullish", probability=25, description="bull", expected_path="up"),
            ScenarioCase(name="bearish", probability=20, description="bear", expected_path="down"),
        ],
        bullish_counterargument="bull",
        bearish_counterargument="bear",
        facts=["fact"],
        assumptions=["assumption"],
        inferences=["inference"],
        data_gaps=["gap"],
        risk_state=RiskState(
            gross_exposure=0.0,
            dd_pct=0.0,
            kill_switch=False,
            per_trade_risk_budget=1000.0,
            remaining_budget=250000.0,
            notes=[],
        ),
    )

    path, body = generator.write(memo)

    assert "## Market Brief" in body
    assert "## Trade Memo" in body
    assert "## Scenario Analysis" in body
    assert "## Counterarguments" in body
    assert "## Risk Controls" in body
    assert "## Data Gaps" in body
    assert path.endswith(".md")
