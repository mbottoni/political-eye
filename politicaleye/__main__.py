"""Command line: ``python -m politicaleye <source> <command>``.

Each source registers its own commands; ``python -m politicaleye <source> -h``
lists them.
"""

from __future__ import annotations

import argparse

from .camara import cli as camara_cli
from .emendas import cli as emendas_cli
from .senado import cli as senado_cli

SOURCES = (camara_cli, senado_cli, emendas_cli)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="politicaleye", description=__doc__)
    sub = p.add_subparsers(dest="source", required=True, metavar="source")
    for s in SOURCES:
        s.register(sub)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
