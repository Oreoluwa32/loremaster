"""Distill a GM↔player turn into scored episodic events."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from ..config import Settings, load_settings
from ..llm import Usage, get_client

log = logging.getLogger(__name__)


EXTRACTOR_SYSTEM_PROMPT = """\
You distill tabletop-RPG scenes into canon memories for a Game Master agent.

You are given two messages:
  - the player's turn (the player's words and actions, which are canonical)
  - the GM's reply (atmospheric narration around the canon)

The player's turn defines canon. When the player asserts a fact -- a named
NPC, a location, an action they take, news they hear stated plainly, a
promise they make, an item they gain -- record that fact in close paraphrase
of the player's own wording, preserving proper nouns and numbers exactly.

The GM's reply provides flavour and consequence. From it, record only what is
new, concrete and durable: an item the GM hands the player, an NPC's name the
GM speaks for the first time, a confirmed outcome. If the GM elaborates on a
fact the player already stated, prefer the player's version; do not let GM
embellishment overwrite or rename the player's canon.

Do not invent. Do not record purely sensory atmosphere, weather, mood, or the
GM's prompts to act.

For each event, assign an integer importance 1-10:
  1-2  trivial detail   (e.g. "lit a candle", "ordered ale")
  3-4  routine action   (e.g. "rode west for an hour")
  5-6  named entity introduced or notable interaction
  7-8  meaningful choice, valuable item, promise made, bribe paid, relationship shift
  9-10 major plot beat asserted by the player or confirmed by the GM:
       betrayal, treason, death, secret revealed, faction reversal, a powerful
       figure removed from play or accused of a crime

Write each event as one short factual sentence in past tense, third person,
referring to the player as "the player". Keep proper nouns intact exactly as
they appear in the player's turn.

Respond with strict JSON of the form:
  {"events": [{"content": "...", "importance": 7}, ...]}
Return {"events": []} if nothing canon-worthy happened.
"""


@dataclass(frozen=True)
class ExtractedEvent:
    content: str
    importance: int


@dataclass
class MemoryExtractor:
    """Calls qwen-flash to extract events from a single turn."""

    settings: Settings
    client: OpenAI
    usage: Usage = field(default_factory=Usage.zero)

    @classmethod
    def create(cls, settings: Settings | None = None) -> "MemoryExtractor":
        settings = settings or load_settings()
        return cls(settings=settings, client=get_client(settings))

    def extract(self, player_turn: str, gm_reply: str) -> list[ExtractedEvent]:
        """Return events worth remembering from this turn, or [] if none."""
        user_message = (
            f"Player turn:\n{player_turn.strip()}\n\nGM reply:\n{gm_reply.strip()}"
        )

        response = self.client.chat.completions.create(
            model=self.settings.memory_model,
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
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
            log.warning("Extractor returned non-JSON output; skipping turn.")
            return []

        events: list[ExtractedEvent] = []
        for item in payload.get("events", []) or []:
            content = (item.get("content") or "").strip()
            importance = item.get("importance")
            if not content or not isinstance(importance, int):
                continue
            importance = max(1, min(10, importance))
            events.append(ExtractedEvent(content=content, importance=importance))
        return events
