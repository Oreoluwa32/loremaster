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

Read the player's turn and the GM's reply. Emit only durable facts a future GM
would want to recall: new or evolving NPCs, locations, factions, quests,
choices with consequences, secrets revealed, items gained or lost, injuries,
promises, betrayals, deaths.

Skip pure sensory atmosphere, generic descriptions of mood or weather, and the
GM's prompts to act.

For each event, assign an integer importance 1-10:
  1-2  trivial detail   (e.g. "lit a candle", "ordered ale")
  3-4  routine action   (e.g. "bought 3 torches", "rode west for an hour")
  5-6  named entity introduced or notable interaction
  7-8  meaningful choice, relationship shift, valuable item
  9-10 major plot beat: betrayal, death, secret revealed, faction reversal

Write each event as one short factual sentence in past tense, third person,
referring to the player as "the player". Keep proper nouns intact.

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
