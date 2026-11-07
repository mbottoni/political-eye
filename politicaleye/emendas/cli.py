"""``python -m politicaleye emendas {update}``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..io import write_sources
from ..paths import REPO
from .build import build
from .fetch import fetch


def cmd_update(a) -> int:
    zip_path = a.raw / "EmendasParlamentares.zip"
    if not a.skip_fetch:
        write_sources(a.data / "sources.json", {"EmendasParlamentares": fetch(a.raw)})
    r = build(zip_path, a.data)
    print(f"emendas: {r['emendas']} amendments, {r['favorecidos']} named recipients", file=sys.stderr)
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("emendas", help="parliamentary amendments: money committed, paid and who received it")
    p.add_argument("--data", type=Path, default=REPO / "data" / "emendas")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download the Portal da Transparência file and rebuild every table")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "emendas")
    u.add_argument("--skip-fetch", action="store_true", help="build from the zip already in --raw")
    u.set_defaults(fn=cmd_update)
