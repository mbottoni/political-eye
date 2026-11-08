"""``python -m politicaleye ref {update,prefeitos}``."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..paths import REPO
from . import politicians, prefeitos


def cmd_update(a) -> int:
    if not a.skip_fetch:
        politicians.fetch(a.raw, list(range(politicians.FIRST_LEG, 59)))
    politicians.build(a.raw, a.data, a.data / "overrides.csv")
    return 0


def cmd_prefeitos(a) -> int:
    if not a.skip_fetch:
        prefeitos.fetch(a.raw)
    prefeitos.build(a.raw, a.data, a.data.parent / "siconfi" / "entes.csv")
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("ref", help="shared reference tables: one politician across sources")
    p.add_argument("--data", type=Path, default=REPO / "data" / "ref")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download the people lists and rebuild data/ref/politicians.csv")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "ref")
    u.add_argument("--skip-fetch", action="store_true", help="build from the files already in --raw")
    u.set_defaults(fn=cmd_update)
    m = sub.add_parser("prefeitos", help="download TSE's municipal candidates and rebuild data/ref/prefeitos.csv")
    m.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "ref")
    m.add_argument("--skip-fetch", action="store_true", help="build from the files already in --raw")
    m.set_defaults(fn=cmd_prefeitos)
