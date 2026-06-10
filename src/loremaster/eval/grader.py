"""Automated grading of GM probe answers against expected canon facts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from ..config import Settings, load_settings
from ..llm import Usage, get_client

log = logging.getLogger(__name__)


GRADER_SYSTEM_PROMPT = """\
You grade a tabletop-RPG Game Master's recall of campaign canon.

You are given:
  - a probe question the player asked,
  - a list of expected facts the correct answer should contain,
  - the GM's actual reply.

Your job is to decide whether the GM's reply contains ALL the expected facts,
allowing for paraphrasing, equivalent wording, and minor reasonable elaboration.
A reply that invents a different name, swaps an entity, contradicts a fact, or
omits one of the expected facts is INCORRECT.

Respond with strict JSON of the form:
  {"correct": true|false, "reason": "<one short sentence>"}
"""


@dataclass(frozen=True)
class GradeResult:
    correct: bool
    reason: str


@dataclass
class Grader:
    settings: Settings
    client: OpenAI
    usage: Usage = field(default_factory=Usage.zero)

    @classmethod
    def create(cls, settings: Settings | None = None) -> "Grader":
        settings = settings or load_settings()
        return cls(settings=settings, client=get_client(settings))

    def grade(
        self, question: str, expected_facts: list[str], reply: str
    ) -> GradeResult:
        user = (
            f"Probe question:\n{question}\n\n"
            f"Expected facts:\n- " + "\n- ".join(expected_facts) + "\n\n"
            f"GM reply:\n{reply}"
        )
        response = self.client.chat.completions.create(
            model=self.settings.memory_model,
            messages=[
                {"role": "system", "content": GRADER_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw = response.choices[0].message.content or "{}"

        raw_usage = response.usage
        self.usage += Usage(
            prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
        )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Grader returned non-JSON output; marking incorrect.")
            return GradeResult(correct=False, reason="grader returned malformed JSON")

        return GradeResult(
            correct=bool(payload.get("correct")),
            reason=str(payload.get("reason", "")).strip(),
        )
