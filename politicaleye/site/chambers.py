"""Summaries for the Câmara and Senado explorers: ``data/site/{camara,senado}/``.

    networks.csv          per month (Câmara) or window (Senado): the graph metrics of networks.py
    members/YYYY.csv      per member and month: degree, cross-party degree, centrality, community, ideal point
    ideal.csv             per party and month: the median ideal point and its quartiles
    disciplina.csv        (Senado) per party and window: votes with party, government and party majority
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .common import csv
from .networks import analyse, ideal_by_party


def _log(msg: str) -> None:
    print(f"[site] {msg}", file=sys.stderr, flush=True)


def _run(chamber: str, data: Path) -> dict:
    if chamber == "camara":
        from ..camara import graphs as g
        member, load = "deputado_id", lambda m: g.load_month(m, data / "camara").votes
    else:
        from ..senado import graphs as g
        member, load = "senador_id", lambda m: g.load_window(m, g.WINDOW, data / "senado").votes
    root = data / chamber
    out = data / "site" / chamber
    rows, members = [], []
    months = g.months(root)
    for i, m in enumerate(months, 1):
        gv, gc = g.graph(m, "covote", data_dir=root), g.graph(m, "cosponsor", data_dir=root)
        row, mem = analyse(gv, gc, load(m), member)
        rows.append({"month": m, "legislatura": g.legislatura(m), **row})
        if len(mem):
            members.append(mem.assign(month=m))
        if i % 24 == 0:
            _log(f"{chamber}: {i}/{len(months)} months")
    net = pd.DataFrame(rows)
    cols = ["month", "legislatura", "nodes", "edges", "density", "modularity_party", "communities", "modularity_louvain",
            "nmi_party", "ari_party", "assortativity_party", "cross_party_share", "cosponsor_nodes", "cosponsor_edges",
            "overlap_jaccard", "qap_r", "qap_p"]
    net = net.reindex(columns=cols).round(4)
    for c in ("nodes", "edges", "communities", "cosponsor_nodes", "cosponsor_edges"):
        net[c] = net[c].astype("Int64")
    csv(net, out / "networks.csv")
    mem = pd.concat(members, ignore_index=True)
    mem = mem[["month", "id", "nome", "partido", "uf", "degree", "cross_degree", "eigen", "community", "pc1"]]
    folder = out / "members"
    keep = set()
    for y, part in mem.groupby(mem.month.str[:4]):
        p = folder / f"{y}.csv"
        csv(part.sort_values(["month", "id"]), p)
        keep.add(p)
    for p in folder.glob("*.csv"):
        if p not in keep:
            p.unlink()
    csv(ideal_by_party(mem).sort_values(["month", "partido"]), out / "ideal.csv")
    report = {"months": len(net), "with_graph": int((net.nodes > 0).sum()), "member_rows": len(mem)}
    if chamber == "senado":
        report["disciplina"] = _senado_discipline(g, data, out)
    return report


def _senado_discipline(g, data: Path, out: Path) -> int:
    from ..senado import orientations as o

    rows, people = [], []
    for m in g.months(data / "senado"):
        d = o.discipline(m, data_dir=data / "senado")
        if d.empty or d.n_party.sum() == 0:
            continue
        people.append(d.assign(month=m))
        s = d.groupby("partido")[["n_votes", "n_party", "n_with_party", "n_gov", "n_with_gov", "n_majority",
                                   "n_with_majority"]].sum()
        s["senadores"] = d.groupby("partido").size()
        s["month"] = m
        rows.append(s.reset_index())
    t = pd.concat(rows, ignore_index=True)
    for a, n in (("with_party", "n_party"), ("with_gov", "n_gov"), ("with_majority", "n_majority")):
        t[a] = (t[f"n_{a}"] / t[n]).where(t[n] > 0).round(4)
    t = t[["month", "partido", "senadores", "n_votes", "n_party", "with_party", "n_gov", "with_gov", "n_majority",
           "with_majority"]].sort_values(["month", "partido"])
    csv(t, out / "disciplina.csv")
    p = pd.concat(people, ignore_index=True)[["month", "senador_id", "nome", "partido", "uf", "n_votes", "n_party",
                                              "with_party", "n_gov", "with_gov", "n_majority", "with_majority"]]
    csv(p.sort_values(["month", "senador_id"]), out / "disciplina_senadores.csv")
    return len(t)


def build_camara(data: Path) -> dict:
    return _run("camara", data)


def build_senado(data: Path) -> dict:
    return _run("senado", data)
