"""``python -m politicaleye site {build,maps}``."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from ..paths import DATA

# page -> module under politicaleye.site with a build(data: Path) -> dict
PAGES = {"camara": "camara", "senado": "senado", "orientacoes": "orientacoes", "emendas": "emendas", "tse": "tse", "sancoes": "sancoes", "deputados": "deputados", "pncp": "pncp", "siconfi": "siconfi", "alertas": "alertas", "ranking": "ranking",
         "mudancas": "mudancas"}   # last: it reads the other pages' summaries


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


def cmd_changes(a) -> int:
    from .mudancas import FONTES, feeds, update
    bad = [f for f in a.sources if f not in FONTES]
    if bad:
        print(f"unknown sources {bad}; known: {list(FONTES)}", file=sys.stderr)
        return 2
    print(f"[site] changes: {update(a.data, a.sources or None)}", file=sys.stderr)
    print(f"[site] feeds: {feeds(a.data)}", file=sys.stderr)
    return 0


def cmd_feeds(a) -> int:
    from .mudancas import feeds
    print(f"[site] feeds: {feeds(a.data)}", file=sys.stderr)
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
    c = sub.add_parser("changes", help="update the change logs of the given sources (data/site/mudancas/; default: all) and rebuild the feeds")
    c.add_argument("sources", nargs="*")
    c.set_defaults(fn=cmd_changes)
    f = sub.add_parser("feeds", help="rebuild the Atom feeds (docs/feeds/) from the change logs as they are")
    f.set_defaults(fn=cmd_feeds)
    m = sub.add_parser("maps", help="download IBGE's meshes and write docs/lib/maps/ (run once)")
    m.set_defaults(fn=cmd_maps)
