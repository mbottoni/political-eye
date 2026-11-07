"""``python -m politicaleye senado {update,summarize,export}``."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from ..io import write_sources
from ..paths import REPO
from . import graphs, summary
from .build import build_year
from .fetch import FIRST_YEAR, fetch_year


def _default_years() -> list[int]:
    # The previous year too: January's runs must still close out December,
    # and the Senado corrects recent records.
    y = dt.datetime.now(dt.UTC).year
    return [y - 1, y]


def _cached(raw: Path, year: int) -> bool:
    return (raw / f"votacao-{year}.json").exists() and (raw / "autoria" / str(year)).is_dir()


def cmd_update(a) -> int:
    years = sorted(set(a.years or _default_years()))
    if any(y < FIRST_YEAR for y in years):
        print(f"years start at {FIRST_YEAR}", file=sys.stderr)
        return 2
    if a.skip_fetch:
        built = [y for y in years if _cached(a.raw, y)]
    else:
        records = {}
        for y in years:
            records.update(fetch_year(y, a.raw))
        write_sources(a.data / "sources.json", records)
        built = years
    for y in built:
        build_year(y, a.raw, a.data)
    graphs._load.cache_clear()
    df = summary.build_index(a.data)
    print(f"built {built}; index has {len(df)} months ({df.month.min()} → {df.month.max()})", file=sys.stderr)
    return 0


def cmd_summarize(a) -> int:
    summary.build_index(a.data)
    return 0


def cmd_export(a) -> int:
    kw = dict(data_dir=a.data)
    if a.kind == "covote":
        e = graphs.covote_edges(a.month, min_shared=a.min_shared, lop=a.lop, **kw)
        if not a.weighted:
            e = e[e.agreement >= a.tau]
    else:
        types = set(a.types.split(",")) if a.types else None
        e = graphs.cosponsor_edges(a.month, max_authors=a.max_authors or None, types=types, exclude=(), **kw)
        if not a.weighted:
            e = e[e.n_items >= a.min_items]
    e.to_csv(sys.stdout, index=False, lineterminator="\n")
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("senado", help="Senado Federal: monthly co-voting and co-authorship graphs")
    p.add_argument("--data", type=Path, default=REPO / "data" / "senado")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("update", help="download, rebuild the given years, refresh index.csv")
    u.add_argument("years", nargs="*", type=int, help="default: previous and current year")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw" / "senado")
    u.add_argument("--skip-fetch", action="store_true", help="build from responses already in --raw")
    u.set_defaults(fn=cmd_update)

    s = sub.add_parser("summarize", help="refresh index.csv only")
    s.set_defaults(fn=cmd_summarize)

    e = sub.add_parser("export", help="print one month's edge list as CSV")
    e.add_argument("month", help="YYYY-MM")
    e.add_argument("--kind", choices=["covote", "cosponsor"], default="covote")
    e.add_argument("--weighted", action="store_true", help="every pair, no threshold")
    e.add_argument("--tau", type=float, default=graphs.TAU)
    e.add_argument("--min-shared", type=int, default=graphs.MIN_SHARED)
    e.add_argument("--lop", type=float, default=graphs.LOP)
    e.add_argument("--min-items", type=int, default=graphs.MIN_ITEMS)
    e.add_argument("--max-authors", type=int, default=graphs.MAX_AUTHORS, help="0 = no cap")
    e.add_argument("--types", default="", help="comma-separated matéria types to keep, e.g. PL,PEC,PLP")
    e.set_defaults(fn=cmd_export)
