"""Network analysis of the co-voting and co-signing graphs, for the explorer pages.

For every month (Câmara) or window (Senado), on the same graphs as
``graph()`` with its defaults:

- per graph: size, density, the modularity of the party partition (how
  much the graph splits along party lines), Louvain communities (fixed seed)
  and how well they match parties (NMI, ARI), party assortativity, the share
  of edges that cross parties, and, for the two graphs on their common
  members, edge overlap (Jaccard) and a QAP correlation with a permutation
  p-value;
- per member: degree, cross-party degree, eigenvector centrality, community
  and position on the first principal component of their votes (the "ideal
  point"), standardised within the month and signed so that PT's mean is
  negative, as the explorer draws it.

Betweenness is not computed: it is too slow for weekly runs over every month.
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pandas as pd

QAP_PERMUTATIONS = 200
SEED = 7


def _contingency(a: list, b: list) -> np.ndarray:
    ia = {v: i for i, v in enumerate(sorted(set(a)))}
    ib = {v: i for i, v in enumerate(sorted(set(b)))}
    m = np.zeros((len(ia), len(ib)))
    for x, y in zip(a, b):
        m[ia[x], ib[y]] += 1
    return m


def nmi(a: list, b: list) -> float:
    """Normalised mutual information (arithmetic mean of the entropies)."""
    m = _contingency(a, b)
    n = m.sum()
    if n == 0:
        return math.nan
    pa, pb, pab = m.sum(1) / n, m.sum(0) / n, m / n
    nz = pab > 0
    mi = (pab[nz] * np.log(pab[nz] / np.outer(pa, pb)[nz])).sum()
    ha, hb = -(pa[pa > 0] * np.log(pa[pa > 0])).sum(), -(pb[pb > 0] * np.log(pb[pb > 0])).sum()
    return float(mi / ((ha + hb) / 2)) if ha + hb > 0 else 1.0


def ari(a: list, b: list) -> float:
    """Adjusted Rand index."""
    m = _contingency(a, b)
    n = m.sum()
    comb = lambda x: x * (x - 1) / 2  # noqa: E731
    s = comb(m).sum()
    sa, sb, total = comb(m.sum(1)).sum(), comb(m.sum(0)).sum(), comb(n)
    expected = sa * sb / total if total else 0
    top = (sa + sb) / 2 - expected
    return float((s - expected) / top) if top else math.nan


def ideal_points(votes: pd.DataFrame, member: str, nodes: list[int], party: dict) -> dict[int, float]:
    """First principal component of the members' contested votes, as the explorer computes it, standardised."""
    from ..graphs import vote_matrix

    ids, _, M = vote_matrix(votes, member=member, lop=0.025, obstruction_as_no=member == "deputado_id")
    row = {d: i for i, d in enumerate(ids)}
    keep = [d for d in nodes if d in row]
    if len(keep) < 3 or M.shape[1] < 2:
        return {}
    X = M[[row[d] for d in keep]].astype(float)
    cast = X != 0
    mean = np.where(cast.sum(0) > 0, (X * cast).sum(0) / np.maximum(cast.sum(0), 1), 0)
    X = np.where(cast, X - mean, 0.0)
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    pc = X @ vt[0]
    skew = (pc ** 3).sum()
    if (skew if abs(skew) > 1e-9 else pc[np.argmax(np.abs(pc))]) < 0:
        pc = -pc
    pt = [pc[i] for i, d in enumerate(keep) if party.get(d) == "PT"]
    if pt and np.mean(pt) > 0:
        pc = -pc
    sd = pc.std()
    return {d: float(pc[i] / sd) if sd > 0 else 0.0 for i, d in enumerate(keep)}


def _eigen(G: nx.Graph, nodes: list[int]) -> dict[int, float]:
    if G.number_of_edges() == 0:
        return {d: 0.0 for d in nodes}
    A = nx.to_numpy_array(G, nodelist=nodes)
    w, v = np.linalg.eigh(A)
    x = np.abs(v[:, -1])
    return {d: float(x[i] / x.max()) if x.max() > 0 else 0.0 for i, d in enumerate(nodes)}


def analyse(gv: nx.Graph, gc: nx.Graph, votes: pd.DataFrame, member: str) -> tuple[dict, pd.DataFrame]:
    """Graph-level metrics and the per-member table for one month or window."""
    row: dict = {"nodes": gv.number_of_nodes(), "edges": gv.number_of_edges(), "cosponsor_nodes": gc.number_of_nodes(),
                 "cosponsor_edges": gc.number_of_edges()}
    nodes = sorted(gv.nodes)
    party = {d: gv.nodes[d].get("party", "") for d in nodes}
    if len(nodes) < 3 or gv.number_of_edges() == 0:
        return row, pd.DataFrame()
    row["density"] = nx.density(gv)
    groups: dict[str, set] = {}
    for d in nodes:
        groups.setdefault(party[d] or "?", set()).add(d)
    row["modularity_party"] = nx.community.modularity(gv, list(groups.values()))
    comms = sorted(nx.community.louvain_communities(gv, seed=SEED), key=lambda c: (-len(c), min(c)))
    row["communities"] = len(comms)
    row["modularity_louvain"] = nx.community.modularity(gv, comms)
    comm = {d: k + 1 for k, c in enumerate(comms) for d in c}
    labels = [party[d] or "?" for d in nodes]
    row["nmi_party"] = nmi(labels, [comm[d] for d in nodes])
    row["ari_party"] = ari(labels, [comm[d] for d in nodes])
    try:
        row["assortativity_party"] = nx.attribute_assortativity_coefficient(gv, "party")
    except (ZeroDivisionError, KeyError):
        row["assortativity_party"] = math.nan
    cross = [(u, v) for u, v in gv.edges if party[u] and party[v] and party[u] != party[v]]
    row["cross_party_share"] = len(cross) / gv.number_of_edges()

    common = sorted(set(gv) & set(gc))
    if len(common) >= 3:
        A = nx.to_numpy_array(gv, nodelist=common)
        B = nx.to_numpy_array(gc, nodelist=common)
        iu = np.triu_indices(len(common), 1)
        a, b = A[iu], B[iu]
        inter, union = ((a > 0) & (b > 0)).sum(), ((a > 0) | (b > 0)).sum()
        row["overlap_jaccard"] = inter / union if union else math.nan
        if a.std() > 0 and b.std() > 0:
            r = float(np.corrcoef(a, b)[0, 1])
            rng = np.random.default_rng(SEED)
            hits = 0
            for _ in range(QAP_PERMUTATIONS):
                p = rng.permutation(len(common))
                bp = B[np.ix_(p, p)][iu]
                if np.corrcoef(a, bp)[0, 1] >= r:
                    hits += 1
            row["qap_r"], row["qap_p"] = r, (hits + 1) / (QAP_PERMUTATIONS + 1)

    deg = dict(gv.degree)
    cross_deg = {d: 0 for d in nodes}
    for u, v in cross:
        cross_deg[u] += 1
        cross_deg[v] += 1
    eig = _eigen(gv, nodes)
    pc1 = ideal_points(votes, member, nodes, party)
    members = pd.DataFrame({
        "id": nodes, "nome": [gv.nodes[d].get("name", "") for d in nodes], "partido": [party[d] for d in nodes],
        "uf": [gv.nodes[d].get("uf", "") for d in nodes], "degree": [deg[d] for d in nodes],
        "cross_degree": [cross_deg[d] for d in nodes], "eigen": [round(eig[d], 4) for d in nodes],
        "community": [comm[d] for d in nodes], "pc1": [round(pc1[d], 4) if d in pc1 else None for d in nodes],
    })
    return row, members


def ideal_by_party(members: pd.DataFrame, min_members: int = 3) -> pd.DataFrame:
    """Median and quartiles of the ideal point per party and month."""
    m = members.dropna(subset=["pc1"])
    g = m.groupby(["month", "partido"]).pc1
    out = pd.DataFrame({"n": g.size(), "q25": g.quantile(0.25), "median": g.median(), "q75": g.quantile(0.75)}).reset_index()
    return out[out.n >= min_members].round(4)
