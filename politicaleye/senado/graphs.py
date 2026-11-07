"""Co-voting and co-authorship graphs of the Senado Federal.

The same graphs as the Câmara's (``politicaleye/graphs.py`` holds the shared
code), built from ``data/senado/``. The Senate rarely splits (about 30
contested roll calls in 2025), so a graph pools the ``window`` months ending
at a month (12 by default), never reaching back before the legislature
began. Graphs are not stored: each is a deterministic function of the tables
and the defaults below, which ``methodology/senado.md`` explains.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from .. import graphs as core
from ..paths import DATA

WINDOW = 12        # months pooled into one graph, ending at the month named
TAU = 0.8          # co-voting: minimum agreement rate for an edge
MIN_SHARED = 10    # co-voting: minimum votes two senators both cast
LOP = 0.025        # co-voting: drop votes whose minority side is smaller than this
MAX_AUTHORS = 20   # co-authorship: ignore items with more senator signers (a PEC needs 27)
MIN_ITEMS = 1      # co-authorship: minimum co-signed items for an edge
EXCLUDE_TYPES: frozenset[str] = frozenset()

REPO_DATA = DATA / "senado"
MEMBER = "senador_id"
ITEM = "processo_id"
legislatura = core.legislatura


def _root(data_dir: str | Path | None) -> str | Path:
    """``data_dir``, else ``$POLITICAL_EYE_DATA/senado``, else this checkout's ``data/senado``."""
    d = data_dir
    if d is None:
        env = os.environ.get("POLITICAL_EYE_DATA")
        d = f"{env.rstrip('/')}/senado" if env else REPO_DATA
    if isinstance(d, str) and d.startswith(("http://", "https://")):
        return d.rstrip("/")
    return Path(d)


def _csv(root: str | Path, rel: str, **kw) -> pd.DataFrame:
    src = f"{root}/{rel}" if isinstance(root, str) else root / rel
    return pd.read_csv(src, keep_default_na=False, **kw)


@dataclass(frozen=True)
class Month:
    """The tidy tables for one month (or a window). Treat the frames as read-only."""

    month: str
    votacoes: pd.DataFrame
    votes: pd.DataFrame
    authorship: pd.DataFrame
    senators: pd.DataFrame
    orientations: pd.DataFrame


@lru_cache(maxsize=64)
def _load(month: str, root: str | Path) -> Month:
    return Month(
        month=month,
        votacoes=_csv(root, f"votacoes/{month}.csv", dtype=str),
        votes=_csv(root, f"votes/{month}.csv", dtype={MEMBER: "int64"} | {
            c: str for c in ("votacao_id", "voto", "partido", "uf")}),
        authorship=_csv(root, f"authorship/{month}.csv", dtype={MEMBER: "int64", ITEM: "int64"} | {
            c: str for c in ("sigla_tipo", "materia", "data_apresentacao", "partido")} | {"lider": "int64"}),
        senators=_csv(root, f"senators/{month}.csv", dtype={
            MEMBER: "int64", "nome": str, "partido": str, "uf": str, "n_votes": "int64", "n_authored": "int64"}),
        orientations=_optional(root, f"orientations/{month}.csv", ["votacao_id", "bancada", "orientacao"]),
    )


def _optional(root, rel: str, cols: list[str]) -> pd.DataFrame:
    try:
        return _csv(root, rel, dtype=str)
    except (FileNotFoundError, OSError):
        return pd.DataFrame(columns=cols, dtype=str)


def load_month(month: str, data_dir: str | Path | None = None) -> Month:
    """Load one month's tables. ``data_dir`` may be a local path or a raw URL."""
    return _load(month, _root(data_dir))


def months(data_dir: str | Path | None = None) -> list[str]:
    """Every month with data, oldest first."""
    root = _root(data_dir)
    if isinstance(root, str):
        return sorted(_csv(root, "index.csv", dtype=str)["month"])
    return sorted({p.stem for sub in ("votes", "authorship") for p in (root / sub).glob("*.csv")})


def legislature_start(month: str) -> str:
    """First month of the legislature in force during ``month`` (legislatures start on 1 February)."""
    return f"{1795 + 4 * legislatura(month)}-02"


def _shift(month: str, k: int) -> str:
    y, m = divmod(int(month[:4]) * 12 + int(month[5:7]) - 1 + k, 12)
    return f"{y:04d}-{m + 1:02d}"


def window_months(month: str, window: int = WINDOW) -> list[str]:
    """The months a graph for ``month`` pools: up to ``window`` ending at it, within its legislature."""
    if window < 1:
        raise ValueError("window must be at least 1")
    start = max(_shift(month, -(window - 1)), legislature_start(month))
    out, m = [], start
    while m <= month:
        out.append(m)
        m = _shift(m, 1)
    return out


@lru_cache(maxsize=32)
def _window(month: str, window: int, root: str | Path) -> Month:
    have = set(months(root))
    ms = [m for m in window_months(month, window) if m in have]
    parts = [_load(m, root) for m in ms]

    def cat(attr: str) -> pd.DataFrame:
        frames = [getattr(p, attr) for p in parts]
        return pd.concat(frames, ignore_index=True) if frames else getattr(_load_empty(), attr)

    senators = cat("senators")
    if len(senators):   # the latest name, party and UF; counts summed over the window
        last = senators.groupby(MEMBER)[["nome", "partido", "uf"]].last()
        n = senators.groupby(MEMBER)[["n_votes", "n_authored"]].sum()
        senators = last.join(n).reset_index()
    return Month(month=month, votacoes=cat("votacoes"), votes=cat("votes"), authorship=cat("authorship"),
                 senators=senators, orientations=cat("orientations"))


@lru_cache(maxsize=1)
def _load_empty() -> Month:
    e = pd.DataFrame
    return Month("", e(columns=["id"]), e(columns=["votacao_id", MEMBER, "voto", "partido", "uf"]),
                 e(columns=[ITEM, "sigla_tipo", "materia", "data_apresentacao", MEMBER, "partido", "lider"]),
                 e(columns=[MEMBER, "nome", "partido", "uf", "n_votes", "n_authored"]),
                 e(columns=["votacao_id", "bancada", "orientacao"]))


def load_window(month: str, window: int = WINDOW, data_dir: str | Path | None = None) -> Month:
    """The tables of every month in :func:`window_months`, concatenated (``senators``: one row each)."""
    return _window(month, window, _root(data_dir))


def vote_matrix(votes: pd.DataFrame, *, lop: float = LOP) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Senators x votações matrix of +1 (yes), -1 (no), 0 (anything else); see :func:`politicaleye.graphs.vote_matrix`."""
    return core.vote_matrix(votes, member=MEMBER, lop=lop, obstruction_as_no=False)


def _covote(month, *, window, min_shared, lop, data_dir):
    return core.covote(load_window(month, window, data_dir).votes, member=MEMBER, min_shared=min_shared,
                       lop=lop, obstruction_as_no=False)


def _cosponsor(month, *, window, max_authors, types, exclude, data_dir):
    return core.cosponsor(load_window(month, window, data_dir).authorship, member=MEMBER, item=ITEM,
                          max_authors=max_authors, types=types, exclude=exclude)


def covote_edges(month: str, *, window: int = WINDOW, min_shared: int = MIN_SHARED, lop: float = LOP,
                 data_dir=None) -> pd.DataFrame:
    """Every senator pair that cast at least ``min_shared`` votes in common: ``u, v, n_shared, n_agree, agreement``."""
    return _covote(month, window=window, min_shared=min_shared, lop=lop, data_dir=data_dir)[1]


def cosponsor_edges(month: str, *, window: int = WINDOW, max_authors: int | None = MAX_AUTHORS, types=None,
                    exclude=EXCLUDE_TYPES, data_dir=None) -> pd.DataFrame:
    """Every senator pair that co-signed at least one matéria (processo): ``u, v, n_items, weight``."""
    return _cosponsor(month, window=window, max_authors=max_authors, types=types, exclude=exclude,
                      data_dir=data_dir)[1]


def graph(month: str, kind: str = "covote", *, window: int = WINDOW, tau: float = TAU,
          min_shared: int = MIN_SHARED, lop: float = LOP, min_items: int = MIN_ITEMS,
          max_authors: int | None = MAX_AUTHORS, types=None, exclude=EXCLUDE_TYPES, data_dir=None) -> nx.Graph:
    """Binary graph for the ``window`` months ending at ``month``; nodes are senator codes (``CodigoParlamentar``).

    ``kind="covote"``: edge when two senators agreed on at least ``tau`` of
    the non-lopsided votes they both cast, given at least ``min_shared``.
    ``kind="cosponsor"``: edge when two senators co-signed at least
    ``min_items`` matérias with at most ``max_authors`` senator signers.
    Graph attributes include ``window_start``, the first month pooled.
    """
    people = load_window(month, window, data_dir).senators
    if kind == "covote":
        params = dict(tau=tau, min_shared=min_shared, lop=lop)
        nodes, edges = _covote(month, window=window, min_shared=min_shared, lop=lop, data_dir=data_dir)
        edges = edges[edges.agreement >= tau]
    elif kind == "cosponsor":
        params = dict(min_items=min_items, max_authors=max_authors,
                      types=",".join(sorted(types)) if types else None,
                      exclude=",".join(sorted(exclude)) if exclude else None)
        nodes, edges = _cosponsor(month, window=window, max_authors=max_authors, types=types, exclude=exclude,
                                  data_dir=data_dir)
        edges = edges[edges.n_items >= min_items]
    else:
        raise ValueError(f"kind must be 'covote' or 'cosponsor', not {kind!r}")
    params |= dict(window=window, window_start=window_months(month, window)[0])
    return core.to_nx(month, kind, nodes, edges, people, member=MEMBER,
                      params={k: v for k, v in params.items() if v is not None})


def aligned(month: str, **kw) -> tuple[nx.Graph, nx.Graph]:
    """Co-voting and co-authorship graphs on the senators present in both."""
    return core.align(graph(month, "covote", **kw), graph(month, "cosponsor", **kw))


def series(kind: str = "covote", start: str | None = None, end: str | None = None,
           **kw) -> Iterator[tuple[str, nx.Graph]]:
    """Yield ``(month, graph)`` for every month in ``[start, end]``."""
    for m in months(kw.get("data_dir")):
        if (start is None or m >= start) and (end is None or m <= end):
            yield m, graph(m, kind, **kw)
