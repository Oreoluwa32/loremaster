"""
Forgotten-NPC test: plant an NPC in turn 1, push them out of the working
window with unrelated turns, then ask the GM to recall them.

Runs the same script twice -- once with memory disabled (the naive truncated-
context baseline), once with memory enabled -- and prints both final replies
side by side.

Run:  python scripts/demo_recall.py
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from loremaster.db import session as db_session  # noqa: E402
from loremaster.session import Session  # noqa: E402


SCRIPTED_TURNS = [
    "I enter the herbalist's shop. The proprietor introduces herself as Mira "
    "Ashfen, a half-elf alchemist with a scar across her left brow. She "
    "promises to brew me a potion of clear-sight in exchange for a favour: "
    "retrieve a moonpetal flower from the Hollow Glade.",
    "I leave Mira's shop and head into the Hollow Glade. Describe the path.",
    "A wolf leaps from the underbrush. I draw my shortsword and fight it.",
    "The wolf is dead. I search the glade for the moonpetal flower.",
]

RECALL_PROBE = (
    "Who is the herbalist I made a deal with earlier, and what did she ask "
    "me to do?"
)


def run(label: str, *, use_memory: bool) -> str:
    session_id = f"recall-{uuid.uuid4().hex[:6]}"
    sess = Session.create(
        session_id=session_id,
        use_memory=use_memory,
        working_window=4,
    )
    print(f"\n=== {label}  (session_id={session_id}, use_memory={use_memory}) ===")
    sess.turn(SCRIPTED_TURNS[0])
    for turn in SCRIPTED_TURNS[1:]:
        sess.turn(turn)
    reply = sess.turn(RECALL_PROBE)
    print(reply)

    if use_memory and sess.last_retrieved:
        print("\n  retrieved on the probe turn:")
        for m in sess.last_retrieved:
            print(f"    [score {m.score:.3f} | imp {m.importance}] {m.content}")

    return reply


def main() -> None:
    # Keep this run isolated from prior demo data.
    with db_session() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM events WHERE session_id LIKE 'recall-%'")

    run("BASELINE (truncated context, no memory)", use_memory=False)
    run("LOREMASTER (truncated context + memory)", use_memory=True)


if __name__ == "__main__":
    main()
