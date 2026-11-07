"""``python -m politicaleye tse {update}``."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from ..io import write_sources
from ..paths import REPO
from .build import build_year
from .fetch import GENERAL, fetch


def _default_years() -> list[int]:
    # The latest general election: its accounts keep being filed and judged
    # for months after the vote.
    y = dt.datetime.now(dt.UTC).year
    return [max(e for e in GENERAL if e <= y)]


def cmd_update(a) -> int:
    years = sorted(set(a.years or _default_years()))
    bad = [y for y in years if y not in GENERAL]
    if bad:
        print(f"not a covered general election: {bad} (covered: {list(GENERAL)})", file=sys.stderr)
        return 2
    for y in years:
        if not a.skip_fetch:
            write_sources(a.data / "sources.json", fetch(y, a.raw))
        build_year(y, a.raw, a.data)
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("tse", help="campaign finance of the general elections (TSE)")
    p.add_argument("--data", type=Path, default=REPO / "data" / "tse")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download an election's files and rebuild its tables")
    u.add_argument("years", nargs="*", type=int, help=f"default: the latest general election; any of {list(GENERAL)}")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "tse")
    u.add_argument("--skip-fetch", action="store_true", help="build from the zips already in --raw")
    u.set_defaults(fn=cmd_update)
