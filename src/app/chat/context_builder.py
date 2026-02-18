from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChatContext:
    run: dict[str, Any]
    snippets: dict[str, str]
    context_text: str
    valid_ids: set[str]


def build_chat_context(run: dict[str, Any]) -> ChatContext:
    memo_body = str(run.get("memo_body") or "")
    sections = _extract_markdown_sections(memo_body)

    quality = run.get("quality") or {}
    issues = quality.get("issues") if isinstance(quality, dict) else []
    issues_text = ", ".join(str(item) for item in issues) if issues else "none"

    snippets: dict[str, str] = {
        "run.id": f"Run ID: {run.get('id', 'unknown')}",
        "run.regime": (
            f"Regime={run.get('regime', 'unknown')} | status={run.get('status', 'unknown')} "
            f"| degraded={run.get('degraded', 'unknown')}"
        ),
        "run.quality.issues": f"Quality issues: {issues_text}",
        "memo.market_brief": sections.get("market brief", "No market brief section found."),
        "memo.trade_memo": sections.get("trade memo", "No trade memo section found."),
        "memo.risk_controls": sections.get("risk controls", "No risk controls section found."),
        "memo.data_gaps": sections.get("data gaps", "No data gaps section found."),
    }

    ordered_ids = [
        "run.id",
        "run.regime",
        "run.quality.issues",
        "memo.market_brief",
        "memo.trade_memo",
        "memo.risk_controls",
        "memo.data_gaps",
    ]
    context_lines: list[str] = []
    for snippet_id in ordered_ids:
        context_lines.append(f"[{snippet_id}]")
        context_lines.append(snippets[snippet_id])
        context_lines.append("")

    return ChatContext(
        run=run,
        snippets=snippets,
        context_text="\n".join(context_lines).strip(),
        valid_ids=set(ordered_ids),
    )


def _extract_markdown_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in markdown.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)

    return {
        heading: "\n".join(lines).strip() if lines else "" for heading, lines in sections.items()
    }
