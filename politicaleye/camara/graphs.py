"""Build monthly co-voting and co-authorship graphs from the tidy tables.

Graphs are not stored; they are a deterministic function of ``data/`` and the
parameters below, and each takes well under a second to build. METHODOLOGY.md
explains every default.
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

from ..paths import DATA

TAU = 0.8          # co-voting: minimum agreement rate for an edge
MIN_SHARED = 10    # co-voting: minimum votes two deputies both cast
LOP = 0.025        # co-voting: drop votes whose minority side is smaller than this
MAX_AUTHORS = 50   # co-authorship: ignore items with more deputy signers (signature drives)
MIN_ITEMS = 1      # co-authorship: minimum co-signed items for an edge
# co-authorship: procedural / administrative item types that only appear in
# the records from 2020-2022 on. Kept out by default so the series has no
# break that comes from bookkeeping rather than politics. See METHODOLOGY.md.
EXCLUDE_TYPES = frozenset({"RPD", "DOC"})

REPO_DATA = DATA / "camara"
SIGN = {"Sim": 1, "Não": -1}


def _root(data_dir: str | Path | None) -> str | Path:
    """The Câmara's data directory: ``data_dir``, else ``$POLITICAL_EYE_DATA/camara``
    (a local path or a raw URL to the repo's ``data/``), else this checkout's."""
    d = data_dir
    if d is None:
        env = os.environ.get("POLITICAL_EYE_DATA")
        d = f"{env.rstrip('/')}/camara" if env else REPO_DATA
    if isinstance(d, str) and d.startswith(("http://", "https://")):
        return d.rstrip("/")
    return Path(d)


def _csv(root: str | Path, rel: str, **kw) -> pd.DataFrame:
    src = f"{root}/{rel}" if isinstance(root, str) else root / rel
    return pd.read_csv(src, keep_default_na=False, **kw)


@dataclass(frozen=True)
class Month:
    """The four tidy tables for one month. Treat the frames as read-only."""

    month: str
    votacoes: pd.DataFrame
    votes: pd.DataFrame
    authorship: pd.DataFrame
    deputies: pd.DataFrame


@lru_cache(maxsize=64)
def _load(month: str, root: str | Path) -> Month:
    return Month(
        month=month,
        votacoes=_csv(root, f"votacoes/{month}.csv", dtype=str),
        votes=_csv(root, f"votes/{month}.csv", dtype={"votacao_id": str, "deputado_id": "int64", "voto": str}),
        authorship=_csv(root, f"authorship/{month}.csv", dtype={
            "proposicao_id": "int64", "sigla_tipo": str, "data_apresentacao": str,
            "deputado_id": "int64", "ordem_assinatura": str, "proponente": str,
        }),
        deputies=_csv(root, f"deputies/{month}.csv", dtype={
            "deputado_id": "int64", "nome": str, "partido": str, "uf": str,
            "n_votes": "int64", "n_authored": "int64",
        }),
    )


def load_month(month: str, data_dir: str | Path | None = None) -> Month:
    """Load one month's tables. ``data_dir`` may be a local path or a raw URL."""
    return _load(month, _root(data_dir))


def months(data_dir: str | Path | None = None) -> list[str]:
    """Every month with data, oldest first."""
    root = _root(data_dir)
    if isinstance(root, str):
        return sorted(_csv(root, "index.csv", dtype=str)["month"])
    return sorted({p.stem for sub in ("votes", "authorship") for p in (root / sub).glob("*.csv")})


def legislatura(month: str) -> int:
    """Legislature number in force during ``month`` (each starts on 1 February)."""
    year, mon = int(month[:4]), int(month[5:7])
    return (year - (1 if mon == 1 else 0) - 1795) // 4


# ---------------------------------------------------------------- co-voting

def vote_matrix(
    votes: pd.DataFrame, *, lop: float = LOP, obstruction_as_no: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Deputies x votações matrix of +1 (yes), -1 (no), 0 (absent or abstained).

    Lopsided votes (minority share below ``lop``) are dropped, then any deputy
    left with no votes. Returns ``(deputy_ids, votacao_ids, M)``.
    """
    sign = votes.voto.map(SIGN)
    if obstruction_as_no:
        sign = sign.mask(votes.voto == "Obstrução", -1)
    ok = sign.notna().to_numpy()
    dep = votes.deputado_id.to_numpy()[ok]
    vid = votes.votacao_id.to_numpy()[ok]
    s = sign.to_numpy()[ok].astype(np.int8)

    deputies = np.unique(dep)
    votacoes = pd.unique(vid)
    col = {v: i for i, v in enumerate(votacoes)}
    M = np.zeros((len(deputies), len(votacoes)), dtype=np.int8)
    M[np.searchsorted(deputies, dep), [col[v] for v in vid]] = s

    yes, no = (M == 1).sum(0), (M == -1).sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        minority = np.minimum(yes, no) / (yes + no)
    keep = (yes + no > 0) & (minority >= lop)
    M = M[:, keep]
    active = (M != 0).any(1)
    return deputies[active], np.asarray(votacoes)[keep], M[active]


def _covote(month: str, *, min_shared: int, lop: float, obstruction_as_no: bool, data_dir):
    ids, _, M = vote_matrix(load_month(month, data_dir).votes, lop=lop, obstruction_as_no=obstruction_as_no)
    A = (M != 0).astype(np.int32)
    P = (M == 1).astype(np.int32)
    N = (M == -1).astype(np.int32)
    shared = A @ A.T
    agree = P @ P.T + N @ N.T
    i, j = np.triu_indices(len(ids), 1)
    s = shared[i, j]
    keep = s >= min_shared
    edges = pd.DataFrame({
        "u": ids[i[keep]], "v": ids[j[keep]],
        "n_shared": s[keep].astype("int64"), "n_agree": agree[i, j][keep].astype("int64"),
    })
    edges["agreement"] = edges.n_agree / edges.n_shared
    nodes = ids[A.sum(1) >= min_shared]
    return nodes, edges


def covote_edges(
    month: str, *, min_shared: int = MIN_SHARED, lop: float = LOP,
    obstruction_as_no: bool = True, data_dir=None,
) -> pd.DataFrame:
    """Every deputy pair that cast at least ``min_shared`` votes in common.

    Columns: ``u, v, n_shared, n_agree, agreement`` with ``u < v``. Threshold
    ``agreement`` yourself, or use :func:`graph`.
    """
    return _covote(month, min_shared=min_shared, lop=lop, obstruction_as_no=obstruction_as_no, data_dir=data_dir)[1]


# ------------------------------------------------------------ co-authorship

def _cosponsor(month: str, *, max_authors: int | None, types, exclude, data_dir):
    au = load_month(month, data_dir).authorship
    if types is not None:
        au = au[au.sigla_tipo.isin(list(types))]
    if exclude:
        au = au[~au.sigla_tipo.isin(list(exclude))]
    nodes = np.unique(au.deputado_id.to_numpy())
    k = au.groupby("proposicao_id").deputado_id.transform("size")
    multi = au[(k >= 2) & ((k <= max_authors) if max_authors is not None else True)]
    cols = ["u", "v", "n_items", "weight"]
    if multi.empty:
        return nodes, pd.DataFrame({c: pd.Series(dtype="int64" if c != "weight" else "float64") for c in cols})

    items = pd.unique(multi.proposicao_id)
    col = {p: n for n, p in enumerate(items)}
    B = np.zeros((len(nodes), len(items)))
    B[np.searchsorted(nodes, multi.deputado_id.to_numpy()), [col[p] for p in multi.proposicao_id]] = 1.0
    size = B.sum(0)
    count = B @ B.T
    newman = (B / (size - 1)) @ B.T
    i, j = np.triu_indices(len(nodes), 1)
    keep = count[i, j] > 0
    return nodes, pd.DataFrame({
        "u": nodes[i[keep]], "v": nodes[j[keep]],
        "n_items": count[i, j][keep].round().astype("int64"),
        "weight": newman[i, j][keep],
    })


def cosponsor_edges(
    month: str, *, max_authors: int | None = MAX_AUTHORS, types=None,
    exclude=EXCLUDE_TYPES, data_dir=None,
) -> pd.DataFrame:
    """Every deputy pair that co-signed at least one proposição.

    Columns: ``u, v, n_items, weight``. ``weight`` is Newman's collaboration
    weight, summing ``1 / (k - 1)`` over co-signed items with ``k`` signers.
    ``types`` keeps only those proposição types (e.g. ``{"PL", "PEC", "PLP"}``);
    ``exclude`` drops types (default ``EXCLUDE_TYPES``; pass ``()`` for all).
    """
    return _cosponsor(month, max_authors=max_authors, types=types, exclude=exclude, data_dir=data_dir)[1]


# ------------------------------------------------------------------- graphs

def _nx(month, kind, nodes, edges, deputies, params) -> nx.Graph:
    G = nx.Graph(month=month, kind=kind, legislatura=legislatura(month), **params)
    info = deputies.set_index("deputado_id")[["nome", "partido", "uf"]]
    for d in sorted(int(n) for n in nodes):
        row = info.loc[d] if d in info.index else None
        G.add_node(d, **({} if row is None else {"name": row.nome, "party": row.partido, "uf": row.uf}))
    attrs = [c for c in edges.columns if c not in ("u", "v")]
    G.add_edges_from(
        (int(r[0]), int(r[1]), dict(zip(attrs, r[2:])))
        for r in edges.itertuples(index=False, name=None)
    )
    return G


def graph(
    month: str,
    kind: str = "covote",
    *,
    tau: float = TAU,
    min_shared: int = MIN_SHARED,
    lop: float = LOP,
    obstruction_as_no: bool = True,
    min_items: int = MIN_ITEMS,
    max_authors: int | None = MAX_AUTHORS,
    types=None,
    exclude=EXCLUDE_TYPES,
    data_dir=None,
) -> nx.Graph:
    """Binary graph for one month; nodes are integer deputy ids.

    ``kind="covote"``: edge when two deputies agreed on at least ``tau`` of
    the (non-lopsided) votes they both cast, given at least ``min_shared``.
    Nodes are deputies with at least ``min_shared`` such votes.

    ``kind="cosponsor"``: edge when two deputies co-signed at least
    ``min_items`` proposições with at most ``max_authors`` deputy signers.
    Nodes are deputies who signed anything (of the selected types) that month.

    Node attributes: ``name, party, uf``. Edge attributes: the columns of
    :func:`covote_edges` / :func:`cosponsor_edges`.
    """
    d = load_month(month, data_dir).deputies
    if kind == "covote":
        params = dict(tau=tau, min_shared=min_shared, lop=lop, obstruction_as_no=obstruction_as_no)
        nodes, edges = _covote(month, min_shared=min_shared, lop=lop,
                               obstruction_as_no=obstruction_as_no, data_dir=data_dir)
        edges = edges[edges.agreement >= tau]
    elif kind == "cosponsor":
        params = dict(min_items=min_items, max_authors=max_authors,
                      types=",".join(sorted(types)) if types else None,
                      exclude=",".join(sorted(exclude)) if exclude else None)
        nodes, edges = _cosponsor(month, max_authors=max_authors, types=types, exclude=exclude, data_dir=data_dir)
        edges = edges[edges.n_items >= min_items]
    else:
        raise ValueError(f"kind must be 'covote' or 'cosponsor', not {kind!r}")
    return _nx(month, kind, nodes, edges, d, {k: v for k, v in params.items() if v is not None})


def aligned(month: str, **kw) -> tuple[nx.Graph, nx.Graph]:
    """Co-voting and co-authorship graphs on the same vertex set.

    The vertex set is the deputies present in both graphs, so the pair is
    ready for a two-graph dependence test. Accepts every :func:`graph` keyword.
    """
    gv = graph(month, "covote", **kw)
    gc = graph(month, "cosponsor", **kw)
    common = sorted(set(gv) & set(gc))
    out = []
    for g in (gv, gc):
        h = nx.Graph(**g.graph)
        h.add_nodes_from((n, g.nodes[n]) for n in common)
        h.add_edges_from(g.subgraph(common).edges(data=True))
        out.append(h)
    return out[0], out[1]


def series(
    kind: str = "covote", start: str | None = None, end: str | None = None, **kw
) -> Iterator[tuple[str, nx.Graph]]:
    """Yield ``(month, graph)`` for every month in ``[start, end]``."""
    for m in months(kw.get("data_dir")):
        if (start is None or m >= start) and (end is None or m <= end):
            yield m, graph(m, kind, **kw)
