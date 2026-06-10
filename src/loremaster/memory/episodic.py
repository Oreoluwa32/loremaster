"""Episodic memory: per-event storage with scored retrieval.

The store also persists *semantic facts* -- consolidated, durable
summaries derived from episodic events -- and unions them into retrieval
so the GM sees both fine-grained moments and stable canon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Sequence

from openai import OpenAI

from ..config import Settings, load_settings
from ..db import session as db_session
from ..embeddings import embed, embed_one
from ..llm import get_client
from .consolidator import ConsolidatedFact, MemoryConsolidator

# Semantic facts are durable by construction; they're stored without an
# explicit importance and presented to the scorer at a fixed high value.
SEMANTIC_IMPORTANCE = 9


MemoryKind = Literal["episodic", "semantic"]


@dataclass(frozen=True)
class RetrievalConfig:
    """Parameters for relevance-gated scoring with importance/recency boosts.

    Cosine similarity is the gating axis; importance and recency act as
    multiplicative tilts so they can break ties between similarly-relevant
    memories without overpowering relevance itself.
    """

    k: int = 8
    candidate_multiplier: int = 6
    importance_boost: float = 0.4
    recency_boost: float = 0.2
    recency_half_life_hours: float = 168.0  # one in-game week of real time


@dataclass(frozen=True)
class Memory:
    """A retrieved memory with its component scores and source kind."""

    id: int
    content: str
    importance: int
    created_at: datetime
    relevance: float
    recency: float
    score: float
    kind: MemoryKind = "episodic"


@dataclass
class EpisodicStore:
    """Reads and writes events and consolidated semantic facts."""

    settings: Settings = field(default_factory=load_settings)
    client: OpenAI | None = None
    consolidator: MemoryConsolidator | None = None

    def __post_init__(self) -> None:
        self.client = self.client or get_client(self.settings)
        self.consolidator = self.consolidator or MemoryConsolidator(
            settings=self.settings, client=self.client
        )

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

    # ---- consolidation ---------------------------------------------------

    def consolidate(self, session_id: str) -> list[ConsolidatedFact]:
        """Distil this session's episodic events into semantic facts."""
        with db_session(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, importance FROM events"
                " WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,),
            )
            episodes = [(eid, content, imp) for eid, content, imp in cur.fetchall()]

        if not episodes:
            return []

        facts = self.consolidator.consolidate(episodes)
        if not facts:
            return []

        vectors = embed(
            [f.content for f in facts], client=self.client, settings=self.settings
        )
        with db_session(self.settings) as conn, conn.cursor() as cur:
            for fact, vector in zip(facts, vectors):
                cur.execute(
                    "INSERT INTO semantic_facts"
                    "   (session_id, content, embedding, source_event_ids)"
                    " VALUES (%s, %s, %s, %s)",
                    (session_id, fact.content, vector, fact.source_event_ids),
                )
        return facts

    def forget(self, session_id: str, *, min_importance: int = 7) -> int:
        """Delete low-importance episodic events for a session.

        Intended to be called after `consolidate()`: anything durable has
        already been captured as a semantic fact, so the leftover routine
        atmosphere can be pruned to keep retrieval focused on canon. Returns
        the number of rows removed.
        """
        with db_session(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM events"
                " WHERE session_id = %s AND importance < %s",
                (session_id, min_importance),
            )
            return cur.rowcount

    # ---- reads ------------------------------------------------------------

    def retrieve(
        self,
        session_id: str,
        query: str,
        *,
        config: RetrievalConfig | None = None,
        now: datetime | None = None,
    ) -> list[Memory]:
        """Return the top-K memories for `query`, unioning episodic + semantic."""
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
            episode_rows = cur.fetchall()

            cur.execute(
                "SELECT id, content, created_at,"
                "       1 - (embedding <=> %s::vector) AS cosine_sim"
                "  FROM semantic_facts"
                " WHERE session_id = %s"
                " ORDER BY embedding <=> %s::vector ASC"
                " LIMIT %s",
                (query_vector, session_id, query_vector, pool_size),
            )
            semantic_rows = cur.fetchall()

        candidates = [
            self._score_episode(row, now=now, config=config) for row in episode_rows
        ] + [
            self._score_semantic(row, now=now, config=config) for row in semantic_rows
        ]
        candidates.sort(key=lambda m: m.score, reverse=True)
        return candidates[: config.k]

    # ---- internals --------------------------------------------------------

    @classmethod
    def _score_episode(
        cls, row, *, now: datetime, config: RetrievalConfig
    ) -> Memory:
        mem_id, content, importance, created_at, cosine_sim = row
        return cls._compose(
            mem_id=mem_id,
            content=content,
            importance=importance,
            created_at=created_at,
            cosine_sim=cosine_sim,
            kind="episodic",
            now=now,
            config=config,
        )

    @classmethod
    def _score_semantic(
        cls, row, *, now: datetime, config: RetrievalConfig
    ) -> Memory:
        mem_id, content, created_at, cosine_sim = row
        return cls._compose(
            mem_id=mem_id,
            content=content,
            importance=SEMANTIC_IMPORTANCE,
            created_at=created_at,
            cosine_sim=cosine_sim,
            kind="semantic",
            now=now,
            config=config,
        )

    @staticmethod
    def _compose(
        *,
        mem_id: int,
        content: str,
        importance: int,
        created_at: datetime,
        cosine_sim: float,
        kind: MemoryKind,
        now: datetime,
        config: RetrievalConfig,
    ) -> Memory:
        relevance = max(0.0, min(1.0, float(cosine_sim)))
        importance_norm = importance / 10.0
        age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
        recency = math.exp(-age_hours / config.recency_half_life_hours)
        boost = (
            1.0
            + config.importance_boost * (importance_norm - 0.5)
            + config.recency_boost * (recency - 0.5)
        )
        return Memory(
            id=mem_id,
            content=content,
            importance=importance,
            created_at=created_at,
            relevance=relevance,
            recency=recency,
            score=relevance * boost,
            kind=kind,
        )
