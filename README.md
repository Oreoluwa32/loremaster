# Loremaster

A Game Master agent that never forgets your campaign.

Loremaster is a Qwen-powered tabletop Game Master built on a **tiered memory
architecture**. A long campaign produces hundreds of NPCs, quests, choices, and
betrayals that quickly overflow any context window — the perfect stress test for
agent memory. Loremaster extracts and importance-scores every event, retrieves
the right memories by *relevance × importance × recency*, and forgets gracefully
by consolidating trivia into compressed summaries while protecting pivotal moments.

Built for the Global AI Hackathon Series with Qwen Cloud — **MemoryAgent** track.

## Status

🚧 Week 1: foundations — Qwen connectivity + project skeleton.

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your key
cp .env.example .env
# then edit .env and paste your Qwen Cloud API key

# 4. Smoke-test the connection
python scripts/hello_qwen.py
```

If step 4 prints a reply from the Game Master, your key and endpoint work.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) (work in progress).

## License

MIT — see [`LICENSE`](LICENSE).
