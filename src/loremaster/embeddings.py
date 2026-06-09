"""Qwen text embeddings via the OpenAI-compatible endpoint."""

from __future__ import annotations

from typing import Sequence

from openai import OpenAI

from .config import Settings, load_settings
from .llm import get_client

# DashScope's embeddings endpoint accepts at most 25 inputs per request for
# text-embedding-v3. We chunk transparently so callers can pass any length.
_MAX_BATCH = 25


def embed(
    texts: Sequence[str],
    *,
    client: OpenAI | None = None,
    settings: Settings | None = None,
) -> list[list[float]]:
    """Return one embedding vector per input string, preserving order."""
    if not texts:
        return []

    settings = settings or load_settings()
    client = client or get_client(settings)

    vectors: list[list[float]] = []
    for start in range(0, len(texts), _MAX_BATCH):
        chunk = list(texts[start : start + _MAX_BATCH])
        response = client.embeddings.create(
            model=settings.embed_model,
            input=chunk,
            dimensions=settings.embed_dim,
        )
        chunk_vectors = [item.embedding for item in response.data]
        if any(len(v) != settings.embed_dim for v in chunk_vectors):
            raise RuntimeError(
                f"Embedding model returned wrong dimension; expected {settings.embed_dim}."
            )
        vectors.extend(chunk_vectors)

    return vectors


def embed_one(
    text: str,
    *,
    client: OpenAI | None = None,
    settings: Settings | None = None,
) -> list[float]:
    """Convenience wrapper for a single string."""
    return embed([text], client=client, settings=settings)[0]
