"""Summaries for the party orientations page: ``data/site/orientacoes/``.

    partidos.csv              per month and party: deputies, votes, with_party, with_gov, with_majority,
                              and the Rice index of cohesion
    deputados/<leg>.csv       per deputy and legislature: the same shares, pooled
    deputados_mes/YYYY.csv    per deputy and month
    orientacoes.csv           per legislature and bench (party, federation, bloc or leadership, as named):
                              how its orientations were given (Sim, Não, Obstrução, Liberado, none) on
                              contested roll calls
    concordancia.csv          per legislature and pair of benches: roll calls where both oriented Sim or
                              Não (Obstrução as Não), and how many times they agreed

All over the contested Plenário votes of the co-voting graph, parties matched
with ``camara.orientations.party_key``. See methodology/camara.md#party-orientations.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from ..camara import graphs as g
from ..camara import orientations as o
from .common import csv

SHARES = (("with_party", "n_party"), ("with_gov", "n_gov"), ("with_majority", "n_majority"))
COUNTS = ["n_votes", "n_party", "n_with_party", "n_gov", "n_with_gov", "n_majority", "n_with_majority"]
MIN_PAIR = 20   # roll calls two benches must both have oriented for their agreement to be shown


def _shares(t: pd.DataFrame) -> pd.DataFrame:
    for a, n in SHARES:
        t[a] = (t[f"n_{a}"] / t[n]).where(t[n] > 0).round(4)
    return t


LEADERS = {"governo": "Governo", "maioria": "Maioria", "minoria": "Minoria", "oposicao": "Oposição"}


def _bench(name: str) -> str:
    b = o.decode(name)
    if b.kind == "leadership":
        return LEADERS[b.leadership]
    if b.kind == "party":
        return o.party_key(name)
    return name


def _rice(votes: pd.DataFrame, kept: set) -> pd.DataFrame:
    """Rice index per party and month: mean over contested roll calls of |yes - no| / (yes + no), parties with 2+ voters."""
    v = votes[votes.votacao_id.isin(kept)].copy()
    v["s"] = v.voto.map({"Sim": 1, "Não": -1, "Obstrução": -1})
    v = v[v.s.notna()]
    v["party"] = v.partido.map(o.party_key)
    by = v.groupby(["votacao_id", "party"]).s.agg(yes=lambda s: (s == 1).sum(), no=lambda s: (s == -1).sum())
    by = by[(by.yes + by.no) >= 2]
    by["rice"] = (by.yes - by.no).abs() / (by.yes + by.no)
    return by.groupby("party").rice.mean()


def build(data: Path) -> dict:
    root = data / "camara"
    out = data / "site" / "orientacoes"
    parties, people, kinds, pairs = [], [], [], {}
    for m in g.months(root):
        d = g.load_month(m, root)
        disc = o.discipline(m, data_dir=root)
        if disc.empty:
            continue
        leg = g.legislatura(m)
        disc = disc.assign(month=m, legislatura=leg, party=disc.partido.map(o.party_key))
        people.append(disc)
        s = disc.groupby("party")[COUNTS].sum()
        s["deputados"] = disc.groupby("party").size()
        _, kept, _ = g.vote_matrix(d.votes)
        kept = set(kept)
        s = s.join(_rice(d.votes, kept).rename("rice"), how="left")
        parties.append(s.reset_index().assign(month=m))

        # How each bench oriented, on contested roll calls: parties under one
        # key, leaderships under one name, federations and blocs as published.
        own = d.orientations[d.orientations.votacao_id.isin(kept)].copy()
        own["party"] = own.bancada.map(_bench)
        own = own.drop_duplicates(["votacao_id", "party"]).assign(value=own.orientacao.replace("", "none"))
        kinds.append(own.groupby(["party", "value"]).size().rename("n").reset_index().assign(legislatura=leg))
        sign = own[own.orientacao.isin(["Sim", "Não", "Obstrução"])].assign(s=lambda t: np.where(t.orientacao == "Sim", 1, -1))
        for _, grp in sign.groupby("votacao_id"):
            pos = dict(zip(grp.party, grp.s))
            for a, b in itertools.combinations(sorted(pos), 2):
                k = (leg, a, b)
                n, agree = pairs.get(k, (0, 0))
                pairs[k] = (n + 1, agree + (pos[a] == pos[b]))

    p = pd.concat(parties, ignore_index=True)
    p = _shares(p).rename(columns={"party": "partido"})
    p["rice"] = p.rice.round(4)
    csv(p[["month", "partido", "deputados", "n_votes", "n_party", "with_party", "n_gov", "with_gov", "n_majority",
           "with_majority", "rice"]].sort_values(["month", "partido"]), out / "partidos.csv")

    pe = pd.concat(people, ignore_index=True)
    cols = ["month", "deputado_id", "nome", "partido", "uf", "n_votes", "with_party", "with_gov", "with_majority"]
    folder = out / "deputados_mes"
    for y, part in pe.groupby(pe.month.str[:4]):
        csv(part[cols].sort_values(["month", "deputado_id"]), folder / f"{y}.csv")
    leg_rows = pe.groupby(["legislatura", "deputado_id"])[COUNTS].sum()
    latest = pe.sort_values("month").groupby(["legislatura", "deputado_id"])[["nome", "partido", "uf"]].last()
    months = pe.groupby(["legislatura", "deputado_id"]).month.nunique().rename("meses")
    leg = _shares(latest.join(leg_rows).join(months).reset_index())
    for lg, part in leg.groupby("legislatura"):
        csv(part[["deputado_id", "nome", "partido", "uf", "meses", "n_votes", "n_party", "with_party", "n_gov", "with_gov",
                  "n_majority", "with_majority"]].sort_values("deputado_id"), out / "deputados" / f"{lg}.csv")

    k = pd.concat(kinds, ignore_index=True).groupby(["legislatura", "party", "value"]).n.sum().reset_index()
    k = k.pivot_table(index=["legislatura", "party"], columns="value", values="n", fill_value=0).reset_index()
    for c in ("Sim", "Não", "Obstrução", "Liberado", "none"):
        if c not in k:
            k[c] = 0
    k = k.rename(columns={"party": "partido", "Sim": "sim", "Não": "nao", "Obstrução": "obstrucao", "Liberado": "liberado"})
    k["total"] = k[["sim", "nao", "obstrucao", "liberado", "none"]].sum(1)
    for c in ("total", "sim", "nao", "obstrucao", "liberado", "none"):
        k[c] = k[c].astype("int64")
    csv(k[["legislatura", "partido", "total", "sim", "nao", "obstrucao", "liberado", "none"]].sort_values(["legislatura", "partido"]),
        out / "orientacoes.csv")

    c = pd.DataFrame([(lg, a, b, n, ag) for (lg, a, b), (n, ag) in pairs.items() if n >= MIN_PAIR],
                     columns=["legislatura", "a", "b", "n", "agree"]).sort_values(["legislatura", "a", "b"])
    csv(c, out / "concordancia.csv")
    return {"months": p.month.nunique(), "deputy_months": len(pe), "pairs": len(c)}
