# Architecture


## Memory model (planned)

Four tiers:

1. **Working memory** — the current scene; always in the prompt.
2. **Episodic memory** — discrete events, embedded + scored by importance.
3. **Semantic memory** — distilled, durable world facts (canon, lore, faction state).
4. **Entity memory** — evolving state cards per NPC / location / faction.

## Memory operations (planned)

- **Write** — extract events + entities after each scene; assign importance (1–10).
- **Retrieve** — rank by *relevance × importance × recency*; pack top-K into a token budget.
- **Forget** — decay low-importance memories; consolidate clusters into summaries.
- **Consolidate** — periodically distil episodic events into semantic facts.

## Stack

- **LLM:** Qwen (Model Studio, OpenAI-compatible API) — `qwen-plus` for narration, `qwen-flash` for memory ops.
- **Store:** PostgreSQL + pgvector (on Alibaba Cloud).
- **Backend:** FastAPI on Alibaba Cloud.
- **Frontend:** minimal chat UI with a live retrieved-memory visualizer.

## Diagram

_TODO: add architecture diagram before submission._
