from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.chat.service import ChatRunNotFoundError, ChatService
from app.core.types import ChatStreamRequest

router = APIRouter()


def get_chat_service(request: Request) -> ChatService:
    return cast(ChatService, request.app.state.chat_service)


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/chat/status")
def get_chat_status(
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict[str, Any]:
    available, reason = service.is_available()
    return {"available": available, "reason": reason}


@router.post("/chat/stream")
def stream_chat(
    payload: ChatStreamRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    available, reason = service.is_available()
    if not available:
        raise HTTPException(status_code=503, detail=reason or "Chat unavailable")

    try:
        prepared = service.prepare_chat(payload)
    except ChatRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def event_stream() -> Iterator[str]:
        yield _sse("meta", {"run": prepared.run_meta})

        parts: list[str] = []
        try:
            for delta in service.stream_answer(prepared):
                parts.append(delta)
                yield _sse("delta", {"text": delta})

            done = service.finalize_answer("".join(parts), prepared)
            yield _sse("done", done.model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": f"Chat stream failed: {exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
