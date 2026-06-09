"""
Interactive Game Master REPL.

Run:  python scripts/play.py

Commands:
  /quit      end the session
  /reset     clear the conversation and start a new scene
  /history   print the running message log
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Ensure non-ASCII narration renders correctly on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from loremaster.session import Session  # noqa: E402


BANNER = (
    "Loremaster  —  /quit, /reset, /history, /memory  "
    "(use /memory to see what was retrieved last turn)."
)


def _print_gm(text: str) -> None:
    print("\nGame Master:")
    print(text)
    print()


def _print_memory(session: Session) -> None:
    if not session.last_retrieved:
        print("(no memories retrieved on the last turn)\n")
        return
    print("\nRetrieved last turn:")
    for m in session.last_retrieved:
        print(f"  [score {m.score:.3f} | imp {m.importance}] {m.content}")
    print()


def _print_history(session: Session) -> None:
    if not session.history:
        print("(no messages yet)\n")
        return
    for msg in session.history:
        speaker = "You" if msg["role"] == "user" else "Game Master"
        print(f"\n[{speaker}]\n{msg['content']}")
    print()


def main() -> None:
    session = Session.create()
    print(BANNER)
    print(f"Model: {session.model}\n")

    _print_gm(session.open_scene())

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break
        if user_input == "/reset":
            session.reset()
            print("(session cleared)\n")
            _print_gm(session.open_scene())
            continue
        if user_input == "/history":
            _print_history(session)
            continue
        if user_input == "/memory":
            _print_memory(session)
            continue

        _print_gm(session.turn(user_input))


if __name__ == "__main__":
    main()
