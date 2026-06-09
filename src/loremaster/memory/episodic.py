"""Episodic memory: per-event storage with scored retrieval."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from openai import OpenAI

from ..config import Settings, load_settings
from ..db import session as db_session
from ..embeddings import embed, embed_one
from ..llm import get_client


@dataclass(frozen=True)
class RetrievalConfig:
    """Parameters for relevance-gated scoring with importance/recency boosts.

    Cosine similarity is the gating axis; importance and recency act as
    multiplicative tilts so they can break ties between similarly-relevant
    memories without overpowering relevance itself.
    """

    k: int = 5
    candidate_multiplier: int = 6
    importance_boost: float = 0.4
    recency_boost: float = 0.2
    recency_half_life_hours: float = 168.0  # one in-game week of real time


@dataclass(frozen=True)
class Memory:
    """A retrieved episodic memory with its component scores."""

    id: int
    content: str
    importance: int
    created_at: datetime
    relevance: float
    recency: float
    score: float


@dataclass
class EpisodicStore:
    """Reads and writes events for a single Loremaster database."""

    settings: Settings = field(default_factory=load_settings)
    client: OpenAI | None = None

    def __post_init__(self) -> None:
        self.client = self.client or get_client(self.settings)

    # ---- writes -----------------------------------------------------------

    def write(self, session_id: str, content: str, importance: int) -> int:
        """Embed and persist a single event. Returns its row id."""
        return self.write_many(session_id, [(content, importance)])[0]

    def write_many(
        self, session_id: str, events: Sequence[tuple[str, int]]
    ) -> list[int]:
        """Embed and persist a batch of events. Returns row ids in order."""
        if not events:
            return []

        for _, imp in events:
            if not 1 <= imp <= 10:
                raise ValueError(f"importance must be 1..10, got {imp}")

        contents = [c for c, _ in events]
        importances = [i for _, i in events]
        vectors = embed(contents, client=self.client, settings=self.settings)

        ids: list[int] = []
        with db_session(self.settings) as conn, conn.cursor() as cur:
            for content, importance, vector in zip(contents, importances, vectors):
                cur.execute(
                    "INSERT INTO events (session_id, content, embedding, importance)"
                    " VALUES (%s, %s, %s, %s) RETURNING id",
                    (session_id, content, vector, importance),
                )
                ids.append(cur.fetchone()[0])
        return ids

    # ---- reads ------------------------------------------------------------

    def retrieve(
        self,
        session_id: str,
        query: str,
        *,
        config: RetrievalConfig | None = None,
        now: datetime | None = None,
    ) -> list[Memory]:
        """Return the top-K events for `query`, ranked by the composite score."""
        config = config or RetrievalConfig()
        now = now or datetime.now(timezone.utc)

        query_vector = embed_one(query, client=self.client, settings=self.settings)
        pool_size = max(config.k * config.candidate_multiplier, config.k)

        with db_session(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, importance, created_at,"
                "       1 - (embedding <=> %s::vector) AS cosine_sim"
                "  FROM events"
                " WHERE session_id = %s"
                " ORDER BY embedding <=> %s::vector ASC"
                " LIMIT %s",
                (query_vector, session_id, query_vector, pool_size),
            )
            rows = cur.fetchall()

        candidates = [
            self._score(row, now=now, config=config) for row in rows
        ]
        candidates.sort(key=lambda m: m.score, reverse=True)
        return candidates[: config.k]

    # ---- internals --------------------------------------------------------

    @staticmethod
    def _score(row, *, now: datetime, config: RetrievalConfig) -> Memory:
        mem_id, content, importance, created_at, cosine_sim = row
        relevance = max(0.0, min(1.0, float(cosine_sim)))
        importance_norm = importance / 10.0

        age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
        recency = math.exp(-age_hours / config.recency_half_life_hours)

        boost = (
            1.0
            + config.importance_boost * (importance_norm - 0.5)
            + config.recency_boost * (recency - 0.5)
        )
        score = relevance * boost
        return Memory(
            id=mem_id,
            content=content,
            importance=importance,
            created_at=created_at,
            relevance=relevance,
            recency=recency,
            score=score,
        )
