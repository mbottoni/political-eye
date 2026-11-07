"""``python -m politicaleye views {update}``."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..camara.graphs import legislatura
from ..paths import DATA
from . import deputados


def cmd_update(a) -> int:
    latest = legislatura(max(p.stem for p in (a.data / "camara" / "votes").glob("*.csv")))
    for leg in a.legislaturas or [latest - 1, latest]:
        deputados.build(leg, a.data)
    return 0


def register(sources: argparse._SubParsersAction) -> None:
    p = sources.add_parser("views", help="tables that join the sources: one row per deputy, ...")
    p.add_argument("--data", type=Path, default=DATA)
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="rebuild data/views/ from the committed tables")
    u.add_argument("legislaturas", nargs="*", type=int, help="default: the current and previous legislature")
    u.set_defaults(fn=cmd_update)
