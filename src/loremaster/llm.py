"""Thin OpenAI-compatible client helpers for the Qwen endpoint."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .config import Settings, load_settings


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def zero(cls) -> "Usage":
        return cls(prompt_tokens=0, completion_tokens=0)

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


def get_client(settings: Settings | None = None) -> OpenAI:
    settings = settings or load_settings()
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


def chat(
    messages: list[dict],
    model: str,
    client: OpenAI | None = None,
    **kwargs,
) -> str:
    """Send a chat completion and return only the reply text."""
    reply, _ = chat_with_usage(messages, model=model, client=client, **kwargs)
    return reply


def chat_with_usage(
    messages: list[dict],
    model: str,
    client: OpenAI | None = None,
    **kwargs,
) -> tuple[str, Usage]:
    """Send a chat completion and return (reply, usage)."""
    client = client or get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs,
    )
    reply = response.choices[0].message.content or ""
    raw_usage = response.usage
    usage = Usage(
        prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
    )
    return reply, usage
