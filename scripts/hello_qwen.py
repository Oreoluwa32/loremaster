"""
Run:  python scripts/hello_qwen.py
"""

import sys
from pathlib import Path

# Make `src/` importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loremaster.config import load_settings  # noqa: E402
from loremaster.llm import chat, get_client  # noqa: E402

GM_SYSTEM = (
    "You are the Game Master for a fantasy tabletop RPG. "
    "Narrate vividly but concisely. End by prompting the player to act."
)


def main() -> None:
    settings = load_settings()
    client = get_client(settings)
    print(f"Connecting to {settings.base_url}\nModel: {settings.gm_model}\n")

    reply = chat(
        messages=[
            {"role": "system", "content": GM_SYSTEM},
            {"role": "user", "content": "Begin a new campaign. Set the opening scene."},
        ],
        model=settings.gm_model,
        client=client,
    )
    print("--- Game Master ---")
    print(reply)


if __name__ == "__main__":
    main()
