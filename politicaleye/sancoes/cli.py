"""``python -m politicaleye sancoes {update}``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..io import write_sources
from ..paths import REPO
from .build import build
from .fetch import fetch


def cmd_update(a) -> int:
    src = a.data / "sources.json"
    if a.skip_fetch:
        records = json.loads(src.read_text()) if src.exists() else {}
    else:
        records = fetch(a.raw)
        write_sources(src, records)
    r = build(a.raw, a.data, {k: v.get("date", "") for k, v in records.items()})
    print(f"sancoes: {r.get('ceis', 0)} CEIS, {r.get('cnep', 0)} CNEP, {r.get('cepim', 0)} CEPIM, "
          f"{r.get('leniencia', 0)} leniency rows; {r['changes_today']} changes", file=sys.stderr)
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("sancoes", help="sanctions lists (CEIS, CNEP, CEPIM, leniency) and their history")
    p.add_argument("--data", type=Path, default=REPO / "data" / "sancoes")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download today's snapshots, rebuild the tables, log what changed")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "sancoes")
    u.add_argument("--skip-fetch", action="store_true", help="build from the zips already in --raw")
    u.set_defaults(fn=cmd_update)
