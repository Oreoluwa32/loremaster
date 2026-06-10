"""Drive a campaign through a memory strategy and grade the recall probes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from ..db import session as db_session
from ..llm import Usage
from ..session import Session
from .campaign import Campaign, Probe
from .grader import GradeResult, Grader

Strategy = Literal["truncated", "loremaster"]


@dataclass(frozen=True)
class ProbeOutcome:
    probe: Probe
    reply: str
    grade: GradeResult


@dataclass
class RunResult:
    campaign_id: str
    strategy: Strategy
    session_id: str
    probes: list[ProbeOutcome] = field(default_factory=list)
    gm_usage: Usage = field(default_factory=Usage.zero)
    grader_usage: Usage = field(default_factory=Usage.zero)

    @property
    def correct(self) -> int:
        return sum(1 for p in self.probes if p.grade.correct)

    @property
    def total(self) -> int:
        return len(self.probes)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def tokens_per_correct(self) -> float:
        return self.gm_usage.total_tokens / self.correct if self.correct else float("inf")


def run_campaign(
    campaign: Campaign,
    strategy: Strategy,
    *,
    grader: Grader,
    working_window: int = 6,
) -> RunResult:
    """Play `campaign` under `strategy`, ask its probes, grade each reply."""
    session_id = f"eval-{campaign.id}-{strategy}-{uuid.uuid4().hex[:6]}"

    sess = Session.create(
        session_id=session_id,
        use_memory=(strategy == "loremaster"),
        working_window=working_window,
    )
    grader_before = grader.usage

    for turn in campaign.turns:
        sess.turn(turn)

    result = RunResult(
        campaign_id=campaign.id,
        strategy=strategy,
        session_id=session_id,
    )

    for probe in campaign.probes:
        reply = sess.turn(probe.question)
        grade = grader.grade(probe.question, probe.expected_facts, reply)
        result.probes.append(ProbeOutcome(probe=probe, reply=reply, grade=grade))

    result.gm_usage = sess.total_usage
    result.grader_usage = Usage(
        prompt_tokens=grader.usage.prompt_tokens - grader_before.prompt_tokens,
        completion_tokens=grader.usage.completion_tokens - grader_before.completion_tokens,
    )
    _purge_session(session_id)
    return result


def _purge_session(session_id: str) -> None:
    """Drop persisted events for this eval run so the DB stays clean."""
    try:
        with db_session() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE session_id = %s", (session_id,))
    except Exception:
        # Best-effort cleanup; do not mask the real run result.
        pass
