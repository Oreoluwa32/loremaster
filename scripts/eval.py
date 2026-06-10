"""
Run the eval harness against one or more scripted campaigns.

Run:  python scripts/eval.py
      python scripts/eval.py --trials 3
      python scripts/eval.py eval/campaigns/ravensreach.json --detail

Prints a markdown results table comparing the truncated baseline vs Loremaster.
With --trials N>1, prints mean recall and stddev across independent runs.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from loremaster.eval import (  # noqa: E402
    AggregateResult,
    Grader,
    RunResult,
    aggregate,
    load_campaign,
    run_campaign,
)

STRATEGIES = ("truncated", "loremaster")


def _print_run_detail(result: RunResult) -> None:
    print(f"\n--- {result.campaign_id} / {result.strategy} ---")
    for i, outcome in enumerate(result.probes, 1):
        mark = "ok" if outcome.grade.correct else "miss"
        print(f"  Q{i} [{mark}] {outcome.probe.question}")
        if not outcome.grade.correct:
            print(f"        reason: {outcome.grade.reason}")
        if outcome.retrieved:
            for m in outcome.retrieved:
                tag = "sem" if m.kind == "semantic" else "epi"
                print(
                    f"        retrieved [{tag} | score {m.score:.3f} | imp {m.importance}] {m.content}"
                )


def _print_single_table(results: list[RunResult]) -> None:
    print("\n## Results\n")
    headers = ["campaign", "strategy", "recall", "acc", "gm_tokens", "tokens / correct"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for r in results:
        tpc = f"{r.tokens_per_correct:,.0f}" if r.correct else "n/a"
        print(
            f"| {r.campaign_id} | {r.strategy} | "
            f"{r.correct}/{r.total} | {r.accuracy:.0%} | "
            f"{r.gm_usage.total_tokens:,} | {tpc} |"
        )


def _print_aggregate_table(aggs: list[AggregateResult]) -> None:
    print(f"\n## Results (N = {aggs[0].trials} trials per cell)\n")
    headers = [
        "campaign", "strategy", "recall (mean ± sd)", "acc",
        "gm_tokens (mean)", "tokens / correct",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for a in aggs:
        tpc = (
            f"{a.mean_tokens_per_correct:,.0f}"
            if a.mean_correct > 0
            else "n/a"
        )
        recall = f"{a.mean_correct:.2f} ± {a.stddev_correct:.2f} / {a.total}"
        print(
            f"| {a.campaign_id} | {a.strategy} | "
            f"{recall} | {a.mean_accuracy:.0%} | "
            f"{a.mean_gm_tokens:,.0f} | {tpc} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "campaigns",
        nargs="*",
        help="Campaign JSON files. Defaults to all under eval/campaigns/.",
    )
    parser.add_argument("--working-window", type=int, default=6)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Print per-probe pass/fail breakdown and retrieved memories.",
    )
    parser.add_argument(
        "--strategy",
        choices=("truncated", "loremaster", "both"),
        default="both",
        help="Restrict the run to a single strategy.",
    )
    args = parser.parse_args()
    strategies = STRATEGIES if args.strategy == "both" else (args.strategy,)

    paths = [Path(p) for p in args.campaigns]
    if not paths:
        paths = sorted((ROOT / "eval" / "campaigns").glob("*.json"))
    if not paths:
        print("No campaigns to run.", file=sys.stderr)
        sys.exit(1)

    grader = Grader.create()
    results: dict[tuple[str, str], list[RunResult]] = defaultdict(list)

    for path in paths:
        campaign = load_campaign(path)
        print(f"\n# {campaign.title}  ({campaign.id})")
        for strategy in strategies:
            for trial in range(1, args.trials + 1):
                label = f"  running {strategy}"
                if args.trials > 1:
                    label += f" (trial {trial}/{args.trials})"
                print(label + "...")
                r = run_campaign(
                    campaign,
                    strategy,
                    grader=grader,
                    working_window=args.working_window,
                )
                results[(campaign.id, strategy)].append(r)
                if args.detail:
                    _print_run_detail(r)

    flat = [r for runs in results.values() for r in runs]
    if args.trials > 1:
        aggs = [aggregate(results[key]) for key in results]
        _print_aggregate_table(aggs)
    else:
        _print_single_table(flat)


if __name__ == "__main__":
    main()
