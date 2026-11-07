"""``python -m politicaleye siconfi {update}``."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..paths import REPO
from .build import update


def cmd_update(a) -> int:
    r = update(a.data, hours=a.hours, years=a.years or None, limit=a.limit)
    if r["stopped"]:   # what was read is saved; say so where the workflow shows it
        print(f"::warning::siconfi stopped early: {r['stopped']}")
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("siconfi", help="municipalities' payroll and cash against the Fiscal Responsibility Law")
    p.add_argument("--data", type=Path, default=REPO / "data" / "siconfi")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="read reports from the queue until the time budget runs out")
    u.add_argument("years", nargs="*", type=int, help="default: 2015 to the current year")
    u.add_argument("--hours", type=float, default=5.0, help="time budget (default 5)")
    u.add_argument("--limit", type=int, default=None, help="stop after this many municipality-years")
    u.set_defaults(fn=cmd_update)
