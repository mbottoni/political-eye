"""``python -m politicaleye ref {update}``."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..paths import REPO
from . import politicians


def cmd_update(a) -> int:
    if not a.skip_fetch:
        politicians.fetch(a.raw, list(range(politicians.FIRST_LEG, 59)))
    politicians.build(a.raw, a.data, a.data / "overrides.csv")
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("ref", help="shared reference tables: one politician across sources")
    p.add_argument("--data", type=Path, default=REPO / "data" / "ref")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download the people lists and rebuild data/ref/politicians.csv")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "ref")
    u.add_argument("--skip-fetch", action="store_true", help="build from the files already in --raw")
    u.set_defaults(fn=cmd_update)
