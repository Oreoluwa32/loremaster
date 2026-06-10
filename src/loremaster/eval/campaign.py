"""Scripted-campaign data model for the eval harness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Probe:
    question: str
    expected_facts: list[str]


@dataclass(frozen=True)
class Campaign:
    id: str
    title: str
    description: str
    turns: list[str]
    probes: list[Probe]


def load_campaign(path: str | Path) -> Campaign:
    """Read a campaign JSON file and return a populated `Campaign`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Campaign(
        id=data["id"],
        title=data["title"],
        description=data.get("description", ""),
        turns=list(data["turns"]),
        probes=[
            Probe(
                question=p["question"],
                expected_facts=list(p["expected_facts"]),
            )
            for p in data["probes"]
        ],
    )
