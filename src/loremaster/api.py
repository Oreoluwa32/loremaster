"""FastAPI surface for the Loremaster Game Master agent."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import session as db_session
from .memory import ConsolidatedFact, Memory
from .session import Session

log = logging.getLogger(__name__)


# ---- request / response models ---------------------------------------------


class CreateSessionRequest(BaseModel):
    system_prompt: str | None = None
    working_window: int = Field(default=6, ge=2, le=64)
    opening_prompt: str = "Begin a new campaign. Set the opening scene."


class CreateSessionResponse(BaseModel):
    session_id: str
    opening_scene: str


class TurnRequest(BaseModel):
    message: str = Field(..., min_length=1)


class MemoryItem(BaseModel):
    kind: str
    id: int
    content: str
    importance: int
    score: float | None = None
    relevance: float | None = None
    recency: float | None = None

    @classmethod
    def from_memory(cls, m: Memory) -> "MemoryItem":
        return cls(
            kind=m.kind,
            id=m.id,
            content=m.content,
            importance=m.importance,
            score=m.score,
            relevance=m.relevance,
            recency=m.recency,
        )


class TurnResponse(BaseModel):
    reply: str
    retrieved: list[MemoryItem]


class FactItem(BaseModel):
    content: str
    source_event_ids: list[int]


class ConsolidateResponse(BaseModel):
    facts: list[FactItem]


class StoredEvent(BaseModel):
    id: int
    content: str
    importance: int


class StoredFact(BaseModel):
    id: int
    content: str
    source_event_ids: list[int]


class MemoryDump(BaseModel):
    session_id: str
    events: list[StoredEvent]
    facts: list[StoredFact]


# ---- session registry ------------------------------------------------------


@dataclass
class SessionRegistry:
    """In-memory store of live Session objects keyed by session_id."""

    sessions: dict[str, Session]

    def __init__(self) -> None:
        self.sessions = {}

    def create(self, request: CreateSessionRequest) -> Session:
        session_id = f"api-{uuid.uuid4().hex[:10]}"
        kwargs = {
            "session_id": session_id,
            "working_window": request.working_window,
        }
        if request.system_prompt:
            kwargs["system_prompt"] = request.system_prompt
        sess = Session.create(**kwargs)
        self.sessions[session_id] = sess
        return sess

    def get(self, session_id: str) -> Session:
        sess = self.sessions.get(session_id)
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown session_id: {session_id}",
            )
        return sess


# ---- auth ------------------------------------------------------------------


def _require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("API_AUTH_TOKEN")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-API-Key header",
        )


# ---- app factory -----------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="Loremaster",
        description="A Game Master agent that never forgets your campaign.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registry = SessionRegistry()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/sessions",
        response_model=CreateSessionResponse,
        dependencies=[Depends(_require_api_key)],
    )
    def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
        sess = registry.create(request)
        opening = sess.open_scene(request.opening_prompt)
        return CreateSessionResponse(
            session_id=sess.session_id, opening_scene=opening
        )

    @app.post(
        "/sessions/{session_id}/turn",
        response_model=TurnResponse,
        dependencies=[Depends(_require_api_key)],
    )
    def take_turn(session_id: str, request: TurnRequest) -> TurnResponse:
        sess = registry.get(session_id)
        reply = sess.turn(request.message)
        return TurnResponse(
            reply=reply,
            retrieved=[MemoryItem.from_memory(m) for m in sess.last_retrieved],
        )

    @app.post(
        "/sessions/{session_id}/consolidate",
        response_model=ConsolidateResponse,
        dependencies=[Depends(_require_api_key)],
    )
    def consolidate(session_id: str) -> ConsolidateResponse:
        sess = registry.get(session_id)
        facts: list[ConsolidatedFact] = sess.store.consolidate(session_id)
        return ConsolidateResponse(
            facts=[
                FactItem(
                    content=f.content,
                    source_event_ids=f.source_event_ids,
                )
                for f in facts
            ]
        )

    @app.get(
        "/sessions/{session_id}/memory",
        response_model=MemoryDump,
        dependencies=[Depends(_require_api_key)],
    )
    def dump_memory(session_id: str) -> MemoryDump:
        # Verify the session is live in this process before reading.
        registry.get(session_id)
        events, facts = _load_session_canon(session_id)
        return MemoryDump(session_id=session_id, events=events, facts=facts)

    web_dir = _locate_web_dir()
    if web_dir is not None:
        app.mount("/ui", StaticFiles(directory=str(web_dir), html=True), name="ui")

        @app.get("/", include_in_schema=False)
        def _root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/ui/")

    return app


def _locate_web_dir() -> Path | None:
    """Find the bundled static UI directory, if any."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "web",  # source layout
        Path("/app/web"),                                       # docker image
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").exists():
            return candidate
    return None


def _load_session_canon(
    session_id: str,
) -> tuple[list[StoredEvent], list[StoredFact]]:
    with db_session() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, content, importance FROM events"
            " WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,),
        )
        events = [
            StoredEvent(id=row[0], content=row[1], importance=row[2])
            for row in cur.fetchall()
        ]

        cur.execute(
            "SELECT id, content, source_event_ids FROM semantic_facts"
            " WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,),
        )
        facts = [
            StoredFact(
                id=row[0],
                content=row[1],
                source_event_ids=list(row[2] or []),
            )
            for row in cur.fetchall()
        ]
    return events, facts


# Module-level instance for uvicorn ("loremaster.api:app").
app = create_app()


# Silence unused-import warning while keeping a type alias available.
__all__: Iterable[str] = ("app", "create_app")
