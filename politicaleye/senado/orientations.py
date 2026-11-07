"""Party and government orientations in the Senado, and party discipline.

The Senado publishes how each party leader, the Government, the Majority,
the Minority, the Opposition and the women's caucus oriented a roll call
(from October 2018, for about half of them). There are no blocs or
federations in these lists, so the orientation that applies to a senator is
their own party's. ``methodology/senado.md`` explains every rule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..camara.orientations import party_key as _camara_key
from . import graphs as g

# Labels the Senado's panel uses that the Câmara's do not.
ALIASES = {"REPUBLICA": "REPUBLICANOS", "PROGRES": "PP", "PROGRESSISTAS": "PP"}
LEADERSHIPS = {"GOVERNO": "governo", "MAIORIA": "maioria", "MINORIA": "minoria", "OPOSIÇÃO": "oposicao",
               "BANC FEM": "bancada_feminina", "B.FEMININA": "bancada_feminina"}
NO_PARTY = {"", "S/PARTIDO", "SEM REGISTRO"}
SIGN = {"SIM": 1, "NÃO": -1, "OBSTRUÇÃO": -1}
FREE = "LIVRE"


def party_key(label: str) -> str:
    k = _camara_key(label)
    return ALIASES.get(k, k)


def _sign(s: pd.Series) -> pd.Series:
    return s.str.upper().map(SIGN)


def discipline(month: str, *, window: int = g.WINDOW, lop: float = g.LOP, data_dir=None) -> pd.DataFrame:
    """How often each senator voted with their party, the Government and their party's majority.

    Over the contested votes of the window ending at ``month`` (the votes
    :func:`graphs.vote_matrix` keeps). Columns: ``senador_id, nome, partido,
    uf, n_votes, n_party`` (votes where their party oriented Sim, Não or
    Obstrução), ``n_with_party, with_party, n_free`` (their party left it
    free), ``n_none`` (no orientation from their party, or no party),
    ``n_gov, n_with_gov, with_gov, n_majority, n_with_majority,
    with_majority`` (against the other senators of their party who voted).
    """
    d = g.load_window(month, window, data_dir)
    _, kept, _ = g.vote_matrix(d.votes, lop=lop)
    v = d.votes[d.votes.votacao_id.isin(set(kept))].copy()
    v["s"] = v.voto.map({"Sim": 1, "Não": -1})
    v = v[v.s.notna()]
    v["party"] = v.partido.fillna("").map(party_key)
    no_party = v.party.isin(NO_PARTY).to_numpy()

    o = d.orientations.copy()
    o["key"] = o.bancada.map(party_key)
    lead = o.key.map(LEADERSHIPS)
    parties = o[lead.isna()].drop_duplicates(["votacao_id", "key"], keep="last")
    v = v.merge(parties[["votacao_id", "key", "orientacao"]].rename(columns={"key": "party"}),
                on=["votacao_id", "party"], how="left")
    v.loc[no_party, "orientacao"] = np.nan
    po = _sign(v.orientacao.fillna(""))
    v["free"] = v.orientacao.str.upper() == FREE
    v["followed"] = po.notna()
    v["none"] = ~v.followed & ~v.free
    v["with_party"] = v.followed & (po == v.s)

    gov = o[lead == "governo"].drop_duplicates("votacao_id", keep="last").set_index("votacao_id").orientacao
    go = _sign(v.votacao_id.map(gov).fillna(""))
    v["gov"] = go.notna()
    v["with_gov"] = v.gov & (go == v.s)

    yes, no = (v.s == 1).astype(int), (v.s == -1).astype(int)
    grp = [v.votacao_id, v.party]
    others = (yes.groupby(grp).transform("sum") - yes) - (no.groupby(grp).transform("sum") - no)
    side = np.sign(others).where(~no_party, 0)
    v["majority"] = side != 0
    v["with_majority"] = v.majority & (side == v.s)

    out = v.groupby(g.MEMBER).agg(
        n_votes=("s", "size"), n_party=("followed", "sum"), n_with_party=("with_party", "sum"),
        n_free=("free", "sum"), n_none=("none", "sum"), n_gov=("gov", "sum"), n_with_gov=("with_gov", "sum"),
        n_majority=("majority", "sum"), n_with_majority=("with_majority", "sum"),
    ).astype("int64")
    with np.errstate(invalid="ignore", divide="ignore"):
        for a, n in (("with_party", "n_party"), ("with_gov", "n_gov"), ("with_majority", "n_majority")):
            out[a] = (out[f"n_{a}"] / out[n]).round(4)
    info = d.senators.set_index(g.MEMBER)[["nome", "partido", "uf"]]
    out = info.reindex(out.index).join(out)
    cols = ["nome", "partido", "uf", "n_votes", "n_party", "n_with_party", "with_party", "n_free", "n_none",
            "n_gov", "n_with_gov", "with_gov", "n_majority", "n_with_majority", "with_majority"]
    return out[cols].reset_index()
