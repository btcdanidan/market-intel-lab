from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.chat.context_builder import ChatContext, build_chat_context
from app.chat.openai_client import OpenAIChatClient
from app.config.settings import Settings
from app.core.types import ChatMessage, ChatStreamDone, ChatStreamRequest
from app.storage.repositories import AnalysisRepository

CITATION_RE = re.compile(r"\[([a-z0-9_.-]+)\]", re.IGNORECASE)

ANALYSIS_KEYWORDS = {
    "analysis",
    "trade",
    "risk",
    "memo",
    "signal",
    "regime",
    "funding",
    "options",
    "valuation",
    "entry",
    "stop",
    "target",
    "drawdown",
    "btc",
    "eth",
    "sol",
    "bnb",
    "xrp",
    "market",
    "run",
}

UNRELATED_KEYWORDS = {
    "python",
    "javascript",
    "typescript",
    "react",
    "dockerfile",
    "kubernetes",
    "leetcode",
    "resume",
    "homework",
    "recipe",
    "code",
    "coding",
    "programming",
}


class ChatUnavailableError(RuntimeError):
    pass


class ChatRunNotFoundError(LookupError):
    pass


@dataclass(slots=True)
class ChatPrepared:
    run_id: str
    run_meta: dict[str, Any]
    context: ChatContext
    messages: list[dict[str, str]]
    scope_override: str | None = None


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: AnalysisRepository,
        openai_client: OpenAIChatClient,
    ):
        self.settings = settings
        self.repository = repository
        self.openai_client = openai_client

    def is_available(self) -> tuple[bool, str | None]:
        if not self.openai_client.is_configured():
            return False, "Chat unavailable: set OPENAI_API_KEY"
        return True, None

    def prepare_chat(self, payload: ChatStreamRequest) -> ChatPrepared:
        run = self.repository.get_run(payload.run_id)
        if run is None:
            raise ChatRunNotFoundError(f"Run {payload.run_id} not found")

        context = build_chat_context(run)
        history = self._truncate_messages(payload.messages)
        scope_override = self._scope_override(payload.question)
        system_prompt = self._build_system_prompt(context)

        model_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        model_messages.extend(
            {"role": message.role, "content": message.content.strip()}
            for message in history
            if message.content.strip()
        )
        model_messages.append({"role": "user", "content": payload.question.strip()})

        run_meta = {
            "id": run.get("id"),
            "status": run.get("status"),
            "regime": run.get("regime"),
            "degraded": run.get("degraded"),
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
        }

        return ChatPrepared(
            run_id=payload.run_id,
            run_meta=run_meta,
            context=context,
            messages=model_messages,
            scope_override=scope_override,
        )

    def stream_answer(self, prepared: ChatPrepared) -> Iterator[str]:
        if prepared.scope_override is not None:
            yield prepared.scope_override
            return

        available, message = self.is_available()
        if not available:
            raise ChatUnavailableError(message or "Chat unavailable")

        yield from self.openai_client.stream_response(
            model=self.settings.openai_chat_model,
            input_messages=prepared.messages,
            temperature=self.settings.openai_chat_temperature,
            max_output_tokens=self.settings.openai_chat_max_output_tokens,
        )

    def finalize_answer(self, answer: str, prepared: ChatPrepared) -> ChatStreamDone:
        citations = self._extract_citations(answer, prepared.context.valid_ids)
        citation_note = None
        if not citations:
            citation_note = "No direct citation available from current run context."

        return ChatStreamDone(
            answer=answer.strip(),
            citations=citations,
            run_id=prepared.run_id,
            model=self.settings.openai_chat_model,
            citation_note=citation_note,
        )

    def _truncate_messages(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        max_messages = max(1, self.settings.chat_max_turns) * 2
        if len(messages) <= max_messages:
            return messages
        return messages[-max_messages:]

    def _scope_override(self, question: str) -> str | None:
        lowered = question.lower()
        if any(token in lowered for token in ANALYSIS_KEYWORDS):
            return None
        if any(token in lowered for token in UNRELATED_KEYWORDS):
            return (
                "I can only answer questions about your analysis runs, trade memos, "
                "signals, and risk controls. Ask about the selected run's regime, "
                "setups, or data quality. [run.id]"
            )
        return None

    def _build_system_prompt(self, context: ChatContext) -> str:
        return (
            "You are a Codex-style analysis assistant inside market-intel-lab. "
            "You must stay scoped to the provided run context and trading analysis only. "
            "Use the snippets below as the source of truth. "
            "Rules: "
            "(1) If answerable, cite one or more snippet IDs in square brackets, "
            "e.g. [memo.risk_controls]. "
            "(2) If not answerable from context, say so explicitly and suggest rerunning analysis. "
            "(3) Reject unrelated coding/general tasks and steer back to run analysis. "
            "(4) Keep answers concise and factual. "
            "Context snippets:\n\n"
            f"{context.context_text}"
        )

    @staticmethod
    def _extract_citations(answer: str, allowed_ids: set[str]) -> list[str]:
        ordered: list[str] = []
        for match in CITATION_RE.findall(answer):
            if match in allowed_ids and match not in ordered:
                ordered.append(match)
        return ordered
