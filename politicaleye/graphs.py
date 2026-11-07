"""Co-voting and co-authorship graphs, the same for every chamber.

A chamber's monthly tables name their legislator column after the chamber
(``deputado_id`` in the Câmara, ``senador_id`` in the Senado); every
function here takes that name as ``member``. Each chamber's ``graphs.py``
holds its defaults, loads its months and calls these.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

SIGN = {"Sim": 1, "Não": -1}


def legislatura(month: str) -> int:
    """Legislature in force during ``month`` (each starts on 1 February)."""
    year, mon = int(month[:4]), int(month[5:7])
    return (year - (1 if mon == 1 else 0) - 1795) // 4


def vote_matrix(
    votes: pd.DataFrame, *, member: str, lop: float, obstruction_as_no: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Members x votações matrix of +1 (yes), -1 (no), 0 (absent or abstained).

    Lopsided votes (minority share below ``lop``) are dropped, then any member
    left with no votes. Returns ``(member_ids, votacao_ids, M)``.
    """
    sign = votes.voto.map(SIGN)
    if obstruction_as_no:
        sign = sign.mask(votes.voto == "Obstrução", -1)
    ok = sign.notna().to_numpy()
    who = votes[member].to_numpy()[ok]
    vid = votes.votacao_id.to_numpy()[ok]
    s = sign.to_numpy()[ok].astype(np.int8)

    ids = np.unique(who)
    votacoes = pd.unique(vid)
    col = {v: i for i, v in enumerate(votacoes)}
    M = np.zeros((len(ids), len(votacoes)), dtype=np.int8)
    M[np.searchsorted(ids, who), [col[v] for v in vid]] = s

    yes, no = (M == 1).sum(0), (M == -1).sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        minority = np.minimum(yes, no) / (yes + no)
    keep = (yes + no > 0) & (minority >= lop)
    M = M[:, keep]
    active = (M != 0).any(1)
    return ids[active], np.asarray(votacoes)[keep], M[active]


def covote(votes: pd.DataFrame, *, member: str, min_shared: int, lop: float, obstruction_as_no: bool):
    """``(nodes, edges)``: every pair that cast at least ``min_shared`` votes in common.

    Edge columns ``u, v, n_shared, n_agree, agreement``; nodes are members
    with at least ``min_shared`` votes.
    """
    ids, _, M = vote_matrix(votes, member=member, lop=lop, obstruction_as_no=obstruction_as_no)
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


def cosponsor(authorship: pd.DataFrame, *, member: str, item: str, max_authors: int | None, types, exclude):
    """``(nodes, edges)``: every pair that co-signed at least one item.

    ``item`` is the column naming the bill. Edge columns ``u, v, n_items,
    weight``, where ``weight`` is Newman's collaboration weight. Nodes are
    every member who signed anything of the selected types.
    """
    au = authorship
    if types is not None:
        au = au[au.sigla_tipo.isin(list(types))]
    if exclude:
        au = au[~au.sigla_tipo.isin(list(exclude))]
    nodes = np.unique(au[member].to_numpy())
    k = au.groupby(item)[member].transform("size")
    multi = au[(k >= 2) & ((k <= max_authors) if max_authors is not None else True)]
    cols = ["u", "v", "n_items", "weight"]
    if multi.empty:
        return nodes, pd.DataFrame({c: pd.Series(dtype="int64" if c != "weight" else "float64") for c in cols})

    items = pd.unique(multi[item])
    col = {p: n for n, p in enumerate(items)}
    B = np.zeros((len(nodes), len(items)))
    B[np.searchsorted(nodes, multi[member].to_numpy()), [col[p] for p in multi[item]]] = 1.0
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


def to_nx(month: str, kind: str, nodes, edges: pd.DataFrame, people: pd.DataFrame, *, member: str,
          params: dict) -> nx.Graph:
    """A networkx graph with ``name, party, uf`` on each node from ``people``."""
    G = nx.Graph(month=month, kind=kind, legislatura=legislatura(month), **params)
    info = people.set_index(member)[["nome", "partido", "uf"]]
    for d in sorted(int(n) for n in nodes):
        row = info.loc[d] if d in info.index else None
        G.add_node(d, **({} if row is None else {"name": row.nome, "party": row.partido, "uf": row.uf}))
    attrs = [c for c in edges.columns if c not in ("u", "v")]
    G.add_edges_from(
        (int(r[0]), int(r[1]), dict(zip(attrs, r[2:])))
        for r in edges.itertuples(index=False, name=None)
    )
    return G


def align(gv: nx.Graph, gc: nx.Graph) -> tuple[nx.Graph, nx.Graph]:
    """Both graphs restricted to the members present in both."""
    common = sorted(set(gv) & set(gc))
    out = []
    for g in (gv, gc):
        h = nx.Graph(**g.graph)
        h.add_nodes_from((n, g.nodes[n]) for n in common)
        h.add_edges_from(g.subgraph(common).edges(data=True))
        out.append(h)
    return out[0], out[1]


def density(n_nodes: int, n_edges: int) -> float:
    return round(2 * n_edges / (n_nodes * (n_nodes - 1)), 4) if n_nodes > 1 else 0.0
