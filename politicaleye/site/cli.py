"""``python -m politicaleye site {build,maps}``."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from ..paths import DATA

# page -> module under politicaleye.site with a build(data: Path) -> dict
PAGES = {}


def cmd_build(a) -> int:
    pages = a.pages or list(PAGES)
    bad = [p for p in pages if p not in PAGES]
    if bad:
        print(f"unknown pages {bad}; known: {sorted(PAGES)}", file=sys.stderr)
        return 2
    for p in pages:
        r = importlib.import_module(f"politicaleye.site.{PAGES[p]}").build(a.data)
        print(f"[site] {p}: {r}", file=sys.stderr)
    return 0


def cmd_maps(a) -> int:
    from .maps import write
    write()
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("site", help="summaries for the explorer pages (data/site/) and their maps")
    p.add_argument("--data", type=Path, default=DATA)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="rebuild the summaries of the given pages (default: all)")
    b.add_argument("pages", nargs="*")
    b.set_defaults(fn=cmd_build)
    m = sub.add_parser("maps", help="download IBGE's meshes and write docs/lib/maps/ (run once)")
    m.set_defaults(fn=cmd_maps)
