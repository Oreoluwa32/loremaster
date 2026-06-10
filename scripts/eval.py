"""
Run the eval harness against one or more scripted campaigns.

Run:  python scripts/eval.py
      python scripts/eval.py eval/campaigns/ravensreach.json

Prints a markdown results table comparing the truncated baseline vs Loremaster.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from loremaster.eval import Grader, RunResult, load_campaign, run_campaign  # noqa: E402

STRATEGIES = ("truncated", "loremaster")


def _print_run_detail(result: RunResult) -> None:
    print(f"\n--- {result.campaign_id} / {result.strategy} ---")
    for i, outcome in enumerate(result.probes, 1):
        mark = "ok" if outcome.grade.correct else "miss"
        print(f"  Q{i} [{mark}] {outcome.probe.question}")
        if not outcome.grade.correct:
            print(f"        reason: {outcome.grade.reason}")


def _print_results_table(results: list[RunResult]) -> None:
    print("\n## Results\n")
    headers = [
        "campaign", "strategy", "recall", "acc",
        "gm_tokens", "tokens / correct",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for r in results:
        tpc = (
            f"{r.tokens_per_correct:,.0f}"
            if r.correct
            else "n/a"
        )
        print(
            f"| {r.campaign_id} | {r.strategy} | "
            f"{r.correct}/{r.total} | {r.accuracy:.0%} | "
            f"{r.gm_usage.total_tokens:,} | {tpc} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "campaigns",
        nargs="*",
        help="Campaign JSON files. Defaults to all under eval/campaigns/.",
    )
    parser.add_argument("--working-window", type=int, default=6)
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Print per-probe pass/fail breakdown.",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in args.campaigns]
    if not paths:
        paths = sorted((ROOT / "eval" / "campaigns").glob("*.json"))
    if not paths:
        print("No campaigns to run.", file=sys.stderr)
        sys.exit(1)

    grader = Grader.create()
    results: list[RunResult] = []

    for path in paths:
        campaign = load_campaign(path)
        print(f"\n# {campaign.title}  ({campaign.id})")
        for strategy in STRATEGIES:
            print(f"  running {strategy}...")
            r = run_campaign(
                campaign,
                strategy,
                grader=grader,
                working_window=args.working_window,
            )
            results.append(r)
            if args.detail:
                _print_run_detail(r)

    _print_results_table(results)


if __name__ == "__main__":
    main()
