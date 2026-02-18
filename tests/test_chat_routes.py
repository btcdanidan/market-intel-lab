import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_analysis import router as analysis_router
from app.api.routes_chat import router as chat_router
from app.chat.context_builder import build_chat_context
from app.chat.service import ChatPrepared, ChatRunNotFoundError
from app.core.types import ChatStreamDone


class AnalysisServiceStub:
    def list_runs(self, limit: int = 20):
        return [
            {
                "id": "run_new",
                "status": "completed",
                "regime": "risk-on",
                "degraded": False,
                "created_at": "2026-02-18T08:00:00Z",
                "completed_at": "2026-02-18T08:00:10Z",
            },
            {
                "id": "run_old",
                "status": "completed",
                "regime": "transition",
                "degraded": False,
                "created_at": "2026-02-17T08:00:00Z",
                "completed_at": "2026-02-17T08:00:10Z",
            },
        ]


class ChatServiceStub:
    def __init__(self, *, available: bool = True, missing_run: bool = False):
        self.available = available
        self.missing_run = missing_run
        self.run = {
            "id": "run_new",
            "status": "completed",
            "regime": "risk-on",
            "degraded": False,
            "quality": {"issues": []},
            "memo_body": "\n".join(
                [
                    "## Market Brief",
                    "- brief",
                    "## Trade Memo",
                    "- trade",
                    "## Risk Controls",
                    "- controls",
                    "## Data Gaps",
                    "- none",
                ]
            ),
        }

    def is_available(self):
        if self.available:
            return True, None
        return False, "Chat unavailable: set OPENAI_API_KEY"

    def prepare_chat(self, payload):
        if self.missing_run:
            raise ChatRunNotFoundError("Run missing")
        context = build_chat_context(self.run)
        return ChatPrepared(
            run_id=payload.run_id,
            run_meta={"id": payload.run_id, "status": "completed"},
            context=context,
            messages=[],
            scope_override=None,
        )

    def stream_answer(self, prepared):
        yield "Hello "
        yield "[run.id]"

    def finalize_answer(self, answer, prepared):
        return ChatStreamDone(
            answer=answer,
            citations=["run.id"],
            run_id=prepared.run_id,
            model="gpt-4.1-mini",
        )


def _parse_sse(raw: str):
    events = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        event = None
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data += line.split(":", 1)[1].strip()
        events.append((event, json.loads(data) if data else {}))
    return events


def test_analysis_runs_endpoint_returns_runs() -> None:
    app = FastAPI()
    app.include_router(analysis_router)
    app.state.analysis_service = AnalysisServiceStub()

    client = TestClient(app)
    response = client.get("/analysis/runs?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["id"] == "run_new"
    assert payload["runs"][1]["id"] == "run_old"


def test_chat_stream_emits_meta_delta_done_sequence() -> None:
    app = FastAPI()
    app.include_router(chat_router)
    app.state.chat_service = ChatServiceStub()

    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={
            "run_id": "run_new",
            "question": "Why this trade?",
            "messages": [],
        },
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert "delta" in names
    assert names[-1] == "done"


def test_chat_stream_returns_404_for_missing_run() -> None:
    app = FastAPI()
    app.include_router(chat_router)
    app.state.chat_service = ChatServiceStub(missing_run=True)

    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={"run_id": "unknown", "question": "Why?", "messages": []},
    )

    assert response.status_code == 404


def test_chat_stream_returns_503_when_unavailable() -> None:
    app = FastAPI()
    app.include_router(chat_router)
    app.state.chat_service = ChatServiceStub(available=False)

    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={"run_id": "run_new", "question": "Why?", "messages": []},
    )

    assert response.status_code == 503
