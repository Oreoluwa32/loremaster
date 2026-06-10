"""Campaign session: GM dialogue with memory-aware context packing."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from openai import OpenAI

from .config import Settings, load_settings
from .llm import Usage, chat_with_usage, get_client
from .memory import EpisodicStore, Memory, MemoryExtractor, RetrievalConfig

log = logging.getLogger(__name__)


GM_SYSTEM_PROMPT = (
    "You are the Game Master for a fantasy tabletop RPG. "
    "Narrate vividly but concisely, in second person. "
    "Track the fiction consistently across turns. "
    "End every reply by inviting the player to act."
)

MEMORY_BLOCK_HEADER = (
    "Canonical campaign facts established in earlier turns. Treat them as "
    "TRUE. Do not contradict them, rename their NPCs, or invent alternative "
    "versions. When answering a player's question about earlier events, "
    "ground your reply in these facts rather than invented detail. Use them "
    "silently; do not list them back to the player verbatim."
)


Message = dict[str, str]


@dataclass
class Session:
    """A single campaign session with memory-aware turn handling."""

    client: OpenAI
    model: str
    store: EpisodicStore
    extractor: MemoryExtractor
    session_id: str = field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}")
    system_prompt: str = GM_SYSTEM_PROMPT
    use_memory: bool = True
    working_window: int = 6
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    history: list[Message] = field(default_factory=list)
    last_retrieved: list[Memory] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage.zero)

    @classmethod
    def create(cls, settings: Settings | None = None, **overrides) -> "Session":
        settings = settings or load_settings()
        client = get_client(settings)
        store = EpisodicStore(settings=settings, client=client)
        extractor = MemoryExtractor(settings=settings, client=client)
        return cls(
            client=client,
            model=settings.gm_model,
            store=store,
            extractor=extractor,
            **overrides,
        )

    # ---- public API -------------------------------------------------------

    def open_scene(
        self, prompt: str = "Begin a new campaign. Set the opening scene."
    ) -> str:
        return self.turn(prompt)

    def turn(self, user_input: str) -> str:
        """Send the player's input, return the GM's reply, persist memory."""
        self.history.append({"role": "user", "content": user_input})

        self.last_retrieved = (
            self._retrieve(user_input) if self.use_memory else []
        )
        messages = self._build_messages()

        reply, usage = chat_with_usage(
            messages=messages, model=self.model, client=self.client
        )
        self.usage += usage
        self.history.append({"role": "assistant", "content": reply})

        if self.use_memory:
            self._extract_and_store(user_input, reply)

        return reply

    @property
    def total_usage(self) -> Usage:
        """All tokens spent by this session: GM replies plus memory ops."""
        return (
            self.usage
            + self.extractor.usage
            + self.store.consolidator.usage
        )

    def reset(self) -> None:
        """Clear in-process history. Persisted memory is not deleted."""
        self.history.clear()
        self.last_retrieved.clear()

    # ---- internals --------------------------------------------------------

    def _retrieve(self, query: str) -> list[Memory]:
        try:
            return self.store.retrieve(
                self.session_id, query, config=self.retrieval
            )
        except Exception as exc:
            log.warning("memory retrieval failed: %s", exc)
            return []

    def _extract_and_store(self, user_input: str, reply: str) -> None:
        try:
            events = self.extractor.extract(user_input, reply)
        except Exception as exc:
            log.warning("memory extraction failed: %s", exc)
            return
        if not events:
            return
        try:
            self.store.write_many(
                self.session_id, [(e.content, e.importance) for e in events]
            )
        except Exception as exc:
            log.warning("memory write failed: %s", exc)

    def _build_messages(self) -> list[Message]:
        messages: list[Message] = [
            {"role": "system", "content": self.system_prompt}
        ]
        if self.use_memory:
            memory_block = self._format_memory_block(self.last_retrieved)
            if memory_block:
                messages.append({"role": "system", "content": memory_block})
        messages.extend(self.history[-self.working_window :])
        return messages

    @staticmethod
    def _format_memory_block(memories: list[Memory]) -> str:
        if not memories:
            return ""
        lines = [f"- {m.content}" for m in memories]
        return MEMORY_BLOCK_HEADER + "\n" + "\n".join(lines)
