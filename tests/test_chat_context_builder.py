from app.chat.context_builder import build_chat_context


def test_build_chat_context_extracts_expected_snippets() -> None:
    run = {
        "id": "run_abc",
        "status": "completed",
        "regime": "risk-on",
        "degraded": False,
        "quality": {"issues": ["BTC:missing_options_data"]},
        "memo_body": "\n".join(
            [
                "## Market Brief",
                "- Risk-on tape",
                "## Trade Memo",
                "- Long BTC",
                "## Risk Controls",
                "- Max gross 2.5x",
                "## Data Gaps",
                "- Missing options for SOL",
            ]
        ),
    }

    context = build_chat_context(run)

    assert "run.id" in context.valid_ids
    assert "run.regime" in context.valid_ids
    assert "memo.market_brief" in context.valid_ids
    assert "memo.trade_memo" in context.valid_ids
    assert "memo.risk_controls" in context.valid_ids
    assert "memo.data_gaps" in context.valid_ids

    assert "Run ID: run_abc" in context.snippets["run.id"]
    assert "Max gross 2.5x" in context.snippets["memo.risk_controls"]
    assert "[memo.trade_memo]" in context.context_text
