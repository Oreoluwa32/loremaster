"""Consolidate episodic events into durable semantic facts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from ..config import Settings, load_settings
from ..llm import Usage, get_client

log = logging.getLogger(__name__)


CONSOLIDATOR_SYSTEM_PROMPT = """\
You compress a list of episodic events from a tabletop RPG campaign into a
short set of durable semantic facts that a future Game Master should always
keep in mind.

You will receive a numbered list of events. Each event has an id.

Your task:
  - Group related events (same NPC, same place, same quest, same faction,
    same item, same promise) into one durable fact per group.
  - Write each fact as one or two short past-tense sentences in third person,
    referring to the player as "the player". Preserve proper nouns exactly.
  - State only what is robust across the campaign so far: persistent
    relationships, established names, completed actions, promises made,
    political shifts, items in the player's possession, debts owed.
  - Discard one-off atmosphere, mood, and unconfirmed visions. A fact must
    be something the GM would still hold true ten turns from now.
  - Record the ids of the source events that support each fact in
    `source_event_ids` so the consolidation is auditable.

Aim for roughly 1 fact per 3-5 episodes. Fewer is fine if the campaign is
short or thematically tight; more is fine if there are several independent
threads. Never invent details not present in the episodes.

Respond with strict JSON of the form:
  {"facts": [
     {"content": "...", "source_event_ids": [12, 17, 19]},
     ...
  ]}
Return {"facts": []} if the events contain nothing durable.
"""


@dataclass(frozen=True)
class ConsolidatedFact:
    content: str
    source_event_ids: list[int]


@dataclass
class MemoryConsolidator:
    """Calls qwen-flash to distil episodic events into semantic facts."""

    settings: Settings
    client: OpenAI
    usage: Usage = field(default_factory=Usage.zero)

    @classmethod
    def create(cls, settings: Settings | None = None) -> "MemoryConsolidator":
        settings = settings or load_settings()
        return cls(settings=settings, client=get_client(settings))

    def consolidate(
        self, events: list[tuple[int, str, int]]
    ) -> list[ConsolidatedFact]:
        """Compress (id, content, importance) episodes into semantic facts."""
        if not events:
            return []

        formatted = "\n".join(
            f"{eid}. [imp {imp}] {content}" for eid, content, imp in events
        )
        response = self.client.chat.completions.create(
            model=self.settings.memory_model,
            messages=[
                {"role": "system", "content": CONSOLIDATOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"Events:\n{formatted}"},
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
            log.warning("Consolidator returned non-JSON output; skipping.")
            return []

        known_ids = {eid for eid, _, _ in events}
        facts: list[ConsolidatedFact] = []
        for item in payload.get("facts", []) or []:
            content = (item.get("content") or "").strip()
            source_ids = [
                i for i in (item.get("source_event_ids") or []) if isinstance(i, int)
            ]
            source_ids = [i for i in source_ids if i in known_ids]
            if not content:
                continue
            facts.append(
                ConsolidatedFact(content=content, source_event_ids=source_ids)
            )
        return facts
