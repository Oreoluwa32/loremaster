"""Drive a campaign through a memory strategy and grade the recall probes."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Literal

from ..db import session as db_session
from ..llm import Usage
from ..memory import Memory
from ..session import Session
from .campaign import Campaign, Probe
from .grader import GradeResult, Grader

Strategy = Literal["truncated", "loremaster"]


@dataclass(frozen=True)
class ProbeOutcome:
    probe: Probe
    reply: str
    grade: GradeResult
    retrieved: list[Memory] = field(default_factory=list)


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

    if strategy == "loremaster":
        sess.store.consolidate(session_id)
        sess.store.forget(session_id, min_importance=7)

    result = RunResult(
        campaign_id=campaign.id,
        strategy=strategy,
        session_id=session_id,
    )

    for probe in campaign.probes:
        reply = sess.turn(probe.question)
        grade = grader.grade(probe.question, probe.expected_facts, reply)
        result.probes.append(
            ProbeOutcome(
                probe=probe,
                reply=reply,
                grade=grade,
                retrieved=list(sess.last_retrieved),
            )
        )

    result.gm_usage = sess.total_usage
    result.grader_usage = Usage(
        prompt_tokens=grader.usage.prompt_tokens - grader_before.prompt_tokens,
        completion_tokens=grader.usage.completion_tokens - grader_before.completion_tokens,
    )
    _purge_session(session_id)
    return result


@dataclass(frozen=True)
class AggregateResult:
    """Mean and stddev across N independent runs of the same (campaign, strategy)."""

    campaign_id: str
    strategy: Strategy
    trials: int
    mean_correct: float
    stddev_correct: float
    total: int
    mean_gm_tokens: float

    @property
    def mean_accuracy(self) -> float:
        return self.mean_correct / self.total if self.total else 0.0

    @property
    def mean_tokens_per_correct(self) -> float:
        if self.mean_correct <= 0:
            return float("inf")
        return self.mean_gm_tokens / self.mean_correct


def aggregate(results: list[RunResult]) -> AggregateResult:
    """Reduce N RunResults for the same (campaign, strategy) into mean/stddev."""
    if not results:
        raise ValueError("aggregate() requires at least one result")
    n = len(results)
    correct = [r.correct for r in results]
    tokens = [r.gm_usage.total_tokens for r in results]
    mean_c = sum(correct) / n
    var_c = sum((c - mean_c) ** 2 for c in correct) / n
    return AggregateResult(
        campaign_id=results[0].campaign_id,
        strategy=results[0].strategy,
        trials=n,
        mean_correct=mean_c,
        stddev_correct=math.sqrt(var_c),
        total=results[0].total,
        mean_gm_tokens=sum(tokens) / n,
    )


def _purge_session(session_id: str) -> None:
    """Drop persisted events and semantic facts for this eval run."""
    try:
        with db_session() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE session_id = %s", (session_id,))
            cur.execute(
                "DELETE FROM semantic_facts WHERE session_id = %s", (session_id,)
            )
    except Exception:
        # Best-effort cleanup; do not mask the real run result.
        pass
