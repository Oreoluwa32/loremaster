# Loremaster

A Game Master agent that never forgets your campaign.

Loremaster runs a tabletop role-playing campaign as an AI Game Master, narrating
scenes, voicing NPCs, and adjudicating player choices. Its focus is the hardest
problem in any long-running campaign: **memory**. Over dozens of sessions a world
accumulates hundreds of characters, locations, quests, promises, and grudges —
far more than fits in a model's context window. Loremaster is built around a
memory system designed to keep the *right* details available at the *right*
moment, and to let the rest fade the way a good storyteller's notes would.

## The idea

A campaign is an unusually demanding test of agent memory. The Game Master must
recall a throwaway promise made six sessions ago the instant the player returns to
the village it was made in, while not drowning every prompt in irrelevant history.
Loremaster treats memory as the core engine rather than an add-on:

- Every scene is distilled into discrete events, each scored for how pivotal it is.
- Recall ranks memories by relevance, importance, and recency, and fits the most
  useful ones into a fixed token budget.
- Trivia decays and is consolidated into compact summaries over time, while
  pivotal moments are preserved.

## How memory is organized

| Tier | Holds | Lifetime |
|------|-------|----------|
| Working | The current scene | The turn |
| Episodic | Discrete events, embedded and importance-scored | Decays unless reinforced |
| Semantic | Distilled world facts, lore, faction state | Durable |
| Entity | Evolving state cards per NPC, location, and faction | Updated in place |

Four operations move information between tiers: **write** (extract and score new
events), **retrieve** (rank and budget for the current scene), **forget** (decay
and consolidate low-value memories), and **consolidate** (distil episodic events
into durable facts).

## Tech stack

- **Models** — Qwen via Alibaba Cloud Model Studio (OpenAI-compatible API). A
  capable model narrates; a fast, inexpensive model handles high-volume memory
  operations.
- **Storage** — PostgreSQL with pgvector for embedded memory and retrieval.
- **Backend** — FastAPI.

## Getting started

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env               # then edit .env with your API key

# 4. Verify connectivity
python scripts/hello_qwen.py
```

A narrated opening scene confirms your credentials and endpoint are working.

## Project layout

```
src/loremaster/      Core package (config, model client, memory engine)
scripts/             Runnable entry points and utilities
docs/                Design notes and diagrams
```

## Status

Active development. The model client and campaign loop are in place; the tiered
memory engine and its evaluation harness are landing next.

## License

Released under the MIT License. See [LICENSE](LICENSE).
