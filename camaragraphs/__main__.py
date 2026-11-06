"""Command line: ``python -m camaragraphs {update,summarize,export}``."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import graphs, summary
from .build import build_year
from .fetch import fetch_years

REPO = Path(__file__).resolve().parent.parent


def _default_years() -> list[int]:
    # The previous year too: the Câmara keeps correcting recent records, and
    # January's runs must still close out December.
    y = dt.datetime.now(dt.UTC).year
    return [y - 1, y]


def _write_sources(path: Path, sources) -> None:
    old = json.loads(path.read_text()) if path.exists() else {}
    for s in sources:
        old[f"{s.dataset}-{s.year}"] = asdict(s)
    path.write_text(json.dumps(dict(sorted(old.items())), indent=2, ensure_ascii=False) + "\n")


def cmd_update(a) -> int:
    years = sorted(set(a.years or _default_years()))
    if a.skip_fetch:
        built = [y for y in years if all((a.raw / f"{d}-{y}.csv").exists() for d in
                                         ("votacoes", "votacoesVotos", "proposicoes", "proposicoesAutores"))]
    else:
        sources = fetch_years(years, a.raw)
        built = sorted({s.year for s in sources})
        _write_sources(a.data / "sources.json", sources)
    for y in built:
        build_year(y, a.raw, a.data)
    graphs._load.cache_clear()
    df = summary.build_index(a.data)
    summary.update_readme(a.readme, df)
    print(f"built {built}; index has {len(df)} months ({df.month.min()} → {df.month.max()})", file=sys.stderr)
    return 0


def cmd_summarize(a) -> int:
    df = summary.build_index(a.data)
    summary.update_readme(a.readme, df)
    return 0


def cmd_figures(a) -> int:
    from .figures import render

    month = render(a.data, a.out)
    print(f"figures written to {a.out} (pictured month: {month})", file=sys.stderr)
    return 0


def cmd_export(a) -> int:
    kw = dict(data_dir=a.data)
    if a.kind == "covote":
        e = graphs.covote_edges(a.month, min_shared=a.min_shared, lop=a.lop, **kw)
        if not a.weighted:
            e = e[e.agreement >= a.tau]
    else:
        types = set(a.types.split(",")) if a.types else None
        exclude = set(a.exclude.split(",")) if a.exclude else ()
        e = graphs.cosponsor_edges(a.month, max_authors=a.max_authors or None, types=types, exclude=exclude, **kw)
        if not a.weighted:
            e = e[e.n_items >= a.min_items]
    e.to_csv(sys.stdout, index=False, lineterminator="\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="camaragraphs", description=__doc__)
    p.add_argument("--data", type=Path, default=REPO / "data")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("update", help="download, rebuild the given years, refresh index and README")
    u.add_argument("years", nargs="*", type=int, help="default: previous and current year")
    u.add_argument("--raw", type=Path, default=REPO / ".cache" / "raw")
    u.add_argument("--readme", type=Path, default=REPO / "README.md")
    u.add_argument("--skip-fetch", action="store_true", help="build from files already in --raw")
    u.set_defaults(fn=cmd_update)

    s = sub.add_parser("summarize", help="refresh data/index.csv and README tables only")
    s.add_argument("--readme", type=Path, default=REPO / "README.md")
    s.set_defaults(fn=cmd_summarize)

    f = sub.add_parser("figures", help="render the README charts (needs matplotlib)")
    f.add_argument("--out", type=Path, default=REPO / "figures")
    f.set_defaults(fn=cmd_figures)

    e = sub.add_parser("export", help="print one month's edge list as CSV")
    e.add_argument("month", help="YYYY-MM")
    e.add_argument("--kind", choices=["covote", "cosponsor"], default="covote")
    e.add_argument("--weighted", action="store_true", help="every pair, no threshold")
    e.add_argument("--tau", type=float, default=graphs.TAU)
    e.add_argument("--min-shared", type=int, default=graphs.MIN_SHARED)
    e.add_argument("--lop", type=float, default=graphs.LOP)
    e.add_argument("--min-items", type=int, default=graphs.MIN_ITEMS)
    e.add_argument("--max-authors", type=int, default=graphs.MAX_AUTHORS, help="0 = no cap")
    e.add_argument("--types", default="", help="comma-separated proposição types to keep, e.g. PL,PLP,PEC")
    e.add_argument("--exclude", default=",".join(sorted(graphs.EXCLUDE_TYPES)),
                   help="comma-separated types to drop ('' keeps all)")
    e.set_defaults(fn=cmd_export)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
