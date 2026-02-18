from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class OpenAIClientError(RuntimeError):
    pass


class OpenAIChatClient:
    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self._client: Any | None = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def stream_response(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        temperature: float,
        max_output_tokens: int,
    ) -> Iterator[str]:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is missing")

        client = self._get_client()
        saw_delta = False

        try:
            with client.responses.stream(
                model=model,
                input=input_messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ) as stream:
                for event in stream:
                    event_type = self._event_value(event, "type")
                    if event_type in {
                        "response.output_text.delta",
                        "response.refusal.delta",
                    }:
                        delta = self._event_value(event, "delta")
                        if delta:
                            saw_delta = True
                            yield str(delta)

                final_response = stream.get_final_response()

            if not saw_delta:
                fallback = self._extract_output_text(final_response)
                if fallback:
                    yield fallback
        except Exception as exc:  # noqa: BLE001
            raise OpenAIClientError(f"OpenAI streaming failed: {exc}") from exc

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except Exception as exc:  # noqa: BLE001
            raise OpenAIClientError(f"OpenAI SDK import failed: {exc}") from exc

        self._client = OpenAI(api_key=self.api_key)
        return self._client

    @staticmethod
    def _event_value(event: Any, key: str) -> Any:
        if hasattr(event, key):
            return getattr(event, key)
        if isinstance(event, dict):
            return event.get(key)
        return None

    def _extract_output_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text)

        output = getattr(response, "output", None)
        if not output:
            return ""

        chunks: list[str] = []
        for item in output:
            content = getattr(item, "content", None)
            if not content:
                continue
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(str(text))
        return "".join(chunks).strip()
