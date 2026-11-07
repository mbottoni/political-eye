"""``python -m politicaleye pncp {update}``."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..paths import REPO
from .build import update


def cmd_update(a) -> int:
    r = update(a.data, hours=a.hours, days=a.days)
    if r["stopped"]:
        print(f"::warning::pncp stopped early: {r['stopped']}")
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("pncp", help="public contracts: large ones, those signed with sanctioned companies, daily totals")
    p.add_argument("--data", type=Path, default=REPO / "data" / "pncp")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="read yesterday, then the history until the time budget runs out")
    u.add_argument("--hours", type=float, default=5.0, help="time budget (default 5)")
    u.add_argument("--days", type=int, default=None, help="read at most this many days of history")
    u.set_defaults(fn=cmd_update)
