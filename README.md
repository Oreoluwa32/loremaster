# Loremaster

A Game Master agent that never forgets your campaign.

Loremaster runs a tabletop role-playing campaign as an AI Game Master, narrating
scenes, voicing NPCs, and adjudicating player choices. Its focus is the hardest
problem in any long-running campaign: **memory**. Over dozens of sessions a world
accumulates hundreds of characters, locations, quests, promises, and grudges —
far more than fits in a model's context window. Loremaster is built around a
memory system designed to keep the *right* details available at the *right*
moment, and to let the rest fade the way a good storyteller's notes would.

## Results

On a scripted-campaign benchmark (`eval/campaigns/ravensreach.json`), Loremaster
recovers canon a finite-context baseline cannot, at roughly a fifth of the token
cost per correct recall. Three trials per cell; automated grading by
`qwen-flash`.

| strategy            | recall (mean ± sd)  | accuracy | gm tokens (mean) | tokens / correct |
|---------------------|---------------------|----------|------------------|------------------|
| truncated baseline  | 0.33 ± 0.47 / 4     | 8 %      | 20,067           | 60,200           |
| **Loremaster**      | **3.00 ± 0.82 / 4** | **75 %** | 34,522           | **11,507**       |

Both strategies use the same model, the same campaign, and the same recent-turn
window. The only thing Loremaster adds is the memory system below.

## The idea

A long campaign is an unusually demanding test of agent memory. The Game Master
must recall a throwaway promise made six sessions ago the instant the player
returns to the village it was made in, while not drowning every prompt in
irrelevant history. Loremaster treats memory as the core engine rather than an
add-on:

- Every turn is distilled into discrete events, each scored for how pivotal it is.
- Recall ranks memories by relevance, importance, and recency, then packs the
  best into the prompt.
- Older events are periodically consolidated into compact, durable facts;
  routine atmosphere is forgotten so it stops crowding out canon.

## How memory is organized

| Tier      | Holds                                              | Lifetime                  |
|-----------|----------------------------------------------------|---------------------------|
| Working   | The most recent turns                              | The current scene         |
| Episodic  | Discrete events, embedded and importance-scored    | Decays once consolidated  |
| Semantic  | Distilled durable facts, written by consolidation  | Persistent                |

Four operations move information between tiers:

- **write** — after each turn, `qwen-flash` extracts canon events from the
  player's words and the GM's reply, scoring each 1–10 for importance.
- **retrieve** — at the next turn, the player's input is embedded and used to
  rank memories by `relevance × (importance_boost × recency_boost)`. Top‑K
  enter the prompt as a canonical-facts block.
- **consolidate** — `qwen-flash` groups related episodic events into a small
  set of durable semantic facts, with source‑event ids preserved for audit.
- **forget** — episodic events below an importance threshold are dropped after
  consolidation; their substance lives on in the semantic facts that summarised
  them.

## Tech stack

- **Models** — Qwen via Alibaba Cloud Model Studio (OpenAI-compatible API).
  `qwen-plus` for narration, `qwen-flash` for extraction, consolidation, and
  grading.
- **Storage** — PostgreSQL with pgvector, HNSW indexes for cosine retrieval.
- **Backend** — Python package; a FastAPI surface is in progress.

## Getting started

You will need Python 3.12+, Docker, and a Qwen Model Studio API key.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env               # then edit .env with your API key

# 4. Verify the model connection
python scripts/hello_qwen.py

# 5. Start the database and apply the schema
docker compose up -d
python scripts/init_db.py

# 6. Play a scene
python scripts/play.py             # /quit, /reset, /history, /memory
```

A narrated opening scene confirms your credentials and endpoint are working.
The `/memory` command in `play.py` prints the memory the retriever pulled on
the previous turn — useful for seeing why the GM said what it said.

## Reproducing the results

The eval harness drives the same scripted campaign under two strategies and
grades each probe automatically.

```bash
# Single trial, full per-probe detail (including retrieved memories)
python scripts/eval.py --detail

# Three trials per cell, aggregated as mean ± stddev
python scripts/eval.py --trials 3

# Loremaster only, useful when iterating on the memory system
python scripts/eval.py --strategy loremaster --detail
```

Campaigns live in `eval/campaigns/*.json` and follow a small schema: an ordered
list of narration turns the player sends to the GM, plus probe questions paired
with the canonical facts the answer must contain.

## Project layout

```
src/loremaster/
    config.py        Environment-driven settings (DSN, API key, model ids).
    db.py            Postgres connection helpers.
    embeddings.py    Batched Qwen embeddings.
    llm.py           Thin OpenAI-compatible client with usage accounting.
    schema.sql       Tables and HNSW indexes for events and semantic facts.
    session.py       Memory-aware campaign session.
    memory/          Extractor, consolidator, episodic store.
    eval/            Campaign loader, grader, runner, aggregation.

scripts/             Runnable entry points (play, eval, init_db, demos).
eval/campaigns/      Scripted campaigns with recall probes.
docs/                Design notes and diagrams.
```

## Status

The memory engine, retrieval scoring, consolidation, forgetting, and eval
harness are implemented and producing the numbers above. The remaining work is
a hosted FastAPI deployment, an entity-tier representation for NPCs and
factions, and a richer retrieved-memory visualiser in the demo UI.

## License

Released under the MIT License. See [LICENSE](LICENSE).
