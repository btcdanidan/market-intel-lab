from app.chat.service import ChatRunNotFoundError, ChatService
from app.config.settings import Settings
from app.core.types import ChatMessage, ChatStreamRequest


class FakeRepository:
    def __init__(self):
        self.run = {
            "id": "run_123",
            "status": "completed",
            "regime": "transition",
            "degraded": False,
            "created_at": "2026-02-18T08:00:00Z",
            "completed_at": "2026-02-18T08:00:02Z",
            "quality": {"issues": []},
            "memo_body": "\n".join(
                [
                    "## Market Brief",
                    "- Neutral",
                    "## Trade Memo",
                    "- Long ETH",
                    "## Risk Controls",
                    "- Kill-switch 10%",
                    "## Data Gaps",
                    "- None",
                ]
            ),
        }

    def get_run(self, run_id: str):
        if run_id != "run_123":
            return None
        return self.run


class FakeOpenAIClient:
    def __init__(self):
        self.called = False

    def is_configured(self) -> bool:
        return True

    def stream_response(self, **kwargs):
        self.called = True
        assert kwargs["model"] == "gpt-4.1-mini"
        yield "Answer using "
        yield "[memo.risk_controls]"


def test_prepare_chat_truncates_history_and_builds_context() -> None:
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        CHAT_MAX_TURNS=2,
    )
    service = ChatService(
        settings=settings,
        repository=FakeRepository(),
        openai_client=FakeOpenAIClient(),
    )

    payload = ChatStreamRequest(
        run_id="run_123",
        question="Why this setup?",
        messages=[
            ChatMessage(role="user", content="q1"),
            ChatMessage(role="assistant", content="a1"),
            ChatMessage(role="user", content="q2"),
            ChatMessage(role="assistant", content="a2"),
            ChatMessage(role="user", content="q3"),
        ],
    )

    prepared = service.prepare_chat(payload)

    assert prepared.run_id == "run_123"
    assert prepared.scope_override is None
    assert prepared.messages[0]["role"] == "system"
    assert len(prepared.messages) == 6


def test_finalize_answer_keeps_only_allowed_citations() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")
    service = ChatService(
        settings=settings,
        repository=FakeRepository(),
        openai_client=FakeOpenAIClient(),
    )

    prepared = service.prepare_chat(
        ChatStreamRequest(run_id="run_123", question="risk?", messages=[])
    )

    done = service.finalize_answer(
        "Risk is limited [memo.risk_controls] and [fake.unknown]",
        prepared,
    )

    assert done.citations == ["memo.risk_controls"]
    assert done.citation_note is None


def test_scope_override_rejects_unrelated_question() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")
    fake_client = FakeOpenAIClient()
    service = ChatService(
        settings=settings,
        repository=FakeRepository(),
        openai_client=fake_client,
    )

    prepared = service.prepare_chat(
        ChatStreamRequest(
            run_id="run_123",
            question="Can you write python code for this app?",
            messages=[],
        )
    )

    chunks = list(service.stream_answer(prepared))

    assert prepared.scope_override is not None
    assert chunks
    assert fake_client.called is False


def test_prepare_chat_raises_for_unknown_run() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")
    service = ChatService(
        settings=settings,
        repository=FakeRepository(),
        openai_client=FakeOpenAIClient(),
    )

    try:
        service.prepare_chat(ChatStreamRequest(run_id="missing", question="hello", messages=[]))
    except ChatRunNotFoundError:
        assert True
        return

    raise AssertionError("Expected ChatRunNotFoundError")
