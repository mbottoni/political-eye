"""Party orientations and party discipline.

For each Plenário votação the Câmara publishes how each *bancada* told its
members to vote. A bancada is one of:

- a party (``PT``, ``Solidaried``, ``Novo``);
- a federation of parties, from 2023 (``Fdr PT-PCdoB-PV``);
- a bloc of parties, named by concatenating their abbreviations
  (``PmdbPpPtbPscPhsPen``, ``Bl MdbPsdRepPode``), sometimes cut off
  (``Bl UniPpPsd...``);
- the leadership of the Government (``GOV.`` until 2022, then ``Governo``),
  the Majority, the Minority or the Opposition.

``data/camara/orientations/`` keeps those rows as published. This module
decodes the names, works out which orientation applied to each deputy, and
counts how often deputies followed their party and the government.
``methodology/camara.md`` explains every rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from . import graphs as g

# Orientations a deputy can follow or defy. "Liberado" frees the members; an
# empty orientation means the bancada gave none (seen from 2021 on).
FREE = "Liberado"
LEADERSHIPS = {"GOV.": "governo", "Governo": "governo", "Maioria": "maioria",
               "Minoria": "minoria", "Oposição": "oposicao"}

# Labels are cut to ten characters or so ("Solidaried", "REPUBLIC"), and
# parties were renamed. Renames map to the current name so a label on either
# side of the change matches. Mergers (DEM + PSL -> UNIÃO) are not mapped:
# both parties existed side by side before.
ALIASES = {
    "SOLIDARIED": "SOLIDARIEDADE", "SOLIDARI": "SOLIDARIEDADE", "SD": "SOLIDARIEDADE", "SDD": "SOLIDARIEDADE",
    "REPUBLICAN": "REPUBLICANOS", "REPUBLIC": "REPUBLICANOS", "PODEMOS": "PODE", "PATRI": "PATRIOTA",
    "PP**": "PP",
    # renamed parties
    "PMDB": "MDB", "PR": "PL", "PPS": "CIDADANIA", "PTN": "PODE", "PEN": "PATRIOTA", "PTDOB": "AVANTE",
    "PSDC": "DC", "PRB": "REPUBLICANOS",
}

# Tokens of bloc names, in the CamelCase the Câmara uses.
TOKENS = {
    "Avan": "AVANTE", "Avante": "AVANTE", "Cid": "CIDADANIA", "Dem": "DEM", "Mdb": "MDB", "Novo": "NOVO",
    "Pcdob": "PCDOB", "Pdt": "PDT", "Pen": "PEN", "Phs": "PHS", "Pl": "PL", "Pmdb": "PMDB", "Pmn": "PMN",
    "Pode": "PODE", "Pp": "PP", "Pps": "PPS", "Pr": "PR", "Prb": "PRB", "Prd": "PRD", "Pros": "PROS",
    "Prp": "PRP", "Prtb": "PRTB", "Psb": "PSB", "Psc": "PSC", "Psd": "PSD", "Psdb": "PSDB", "Psdc": "PSDC",
    "Psl": "PSL", "Pt": "PT", "PT": "PT", "Ptb": "PTB", "Ptc": "PTC", "Ptdob": "PTDOB", "PtdoB": "PTDOB",
    "PTdoB": "PTDOB", "Ptn": "PTN", "Pv": "PV", "Rep": "REPUBLICANOS", "Sd": "SOLIDARIEDADE",
    "Solid": "SOLIDARIEDADE", "Uni": "UNIÃO",
}
FEDERATION_MARK = "Fdr"
# A bloc name lists a federation by its first party ("FdrPt"); the members:
FEDERATIONS = {"PT": ("PT", "PCDOB", "PV"), "PSOL": ("PSOL", "REDE"), "PSDB": ("PSDB", "CIDADANIA")}

LEVEL = {"party": 0, "federation": 1, "bloc": 2}


def party_key(label: str) -> str:
    """The key a party label is matched on, the same for votes and orientations."""
    k = label.strip().upper()
    return ALIASES.get(k, k)


@dataclass(frozen=True)
class Bancada:
    name: str
    kind: str                    # party | federation | bloc | leadership
    members: frozenset[str]      # party keys; empty for leaderships
    complete: bool = True        # False when the published name was cut off
    leadership: str | None = None


def _tokens(body: str) -> list[str] | None:
    """Split a CamelCase bloc name into known tokens, or None if it does not parse."""
    out, i, by_len = [], 0, sorted(TOKENS.keys() | {FEDERATION_MARK}, key=len, reverse=True)
    while i < len(body):
        for t in by_len:
            j = i + len(t)
            if body.startswith(t, i) and (j == len(body) or body[j].isupper()):
                out.append(t)
                i = j
                break
        else:
            return None
    return out


@lru_cache(maxsize=None)
def decode(name: str) -> Bancada:
    """What a published bancada name means."""
    if name in LEADERSHIPS:
        return Bancada(name, "leadership", frozenset(), True, LEADERSHIPS[name])
    if name.startswith("Fdr "):
        return Bancada(name, "federation", frozenset(party_key(p) for p in name[4:].split("-")))
    bloc_prefix = name.startswith("Bl ")
    body = name[3:] if bloc_prefix else name
    cut = body.endswith("...")
    body = body.rstrip(".")
    toks = _tokens(body)
    if toks is not None and (bloc_prefix or len(toks) >= 2):
        members, fed = set(), False
        for t in toks:
            if t == FEDERATION_MARK:
                fed = True
                continue
            k = party_key(TOKENS[t])
            members |= set(FEDERATIONS.get(k, (k,))) if fed else {k}
            fed = False
        return Bancada(name, "bloc", frozenset(members), complete=not cut)
    if bloc_prefix or name == "Bloco Parlamentar":
        return Bancada(name, "bloc", frozenset(), complete=False)
    return Bancada(name, "party", frozenset({party_key(name)}))


def _expand(orientations: pd.DataFrame) -> pd.DataFrame:
    """One row per (votação, member party) of every party, federation and bloc row."""
    rows = []
    for vid, name, ori in orientations[["votacao_id", "bancada", "orientacao"]].itertuples(index=False, name=None):
        b = decode(name)
        if b.kind != "leadership":
            rows.extend((vid, p, b.kind, ori) for p in b.members)
    return pd.DataFrame(rows, columns=["votacao_id", "party", "level", "orientacao"]).drop_duplicates()


def applicable(orientations: pd.DataFrame) -> pd.DataFrame:
    """The orientation each party was given in each votação.

    A party's own orientation counts first, then its federation's, then its
    bloc's. An empty orientation passes to the next level; "Liberado" does
    not (the members were freed). If two bancadas at the same level disagree
    for a party, that party has no applicable orientation in that votação.

    Columns: ``votacao_id, party, level, orientacao`` (``party`` is a
    :func:`party_key`; ``level`` is party, federation or bloc).
    """
    cols = ["votacao_id", "party", "level", "orientacao"]
    a = _expand(orientations[orientations.orientacao != ""])
    if a.empty:
        return pd.DataFrame(columns=cols)
    a["_l"] = a.level.map(LEVEL)
    a = a[a._l == a.groupby(["votacao_id", "party"])._l.transform("min")]
    agree = a.groupby(["votacao_id", "party"]).orientacao.transform("nunique") == 1
    return a[agree].drop_duplicates(["votacao_id", "party"])[cols].reset_index(drop=True)


def leadership(orientations: pd.DataFrame, who: str = "governo") -> pd.Series:
    """Orientation of one leadership (governo, maioria, minoria, oposicao) per votação."""
    o = orientations[orientations.bancada.map(lambda n: LEADERSHIPS.get(n)) == who]
    return o[o.orientacao != ""].drop_duplicates("votacao_id").set_index("votacao_id").orientacao


def _sign(s: pd.Series, obstruction_as_no: bool) -> pd.Series:
    m = dict(g.SIGN)
    if obstruction_as_no:
        m["Obstrução"] = -1
    return s.map(m)


def discipline(month: str, *, lop: float = g.LOP, obstruction_as_no: bool = True, data_dir=None) -> pd.DataFrame:
    """How often each deputy voted with their party and with the government.

    Counts contested Plenário votes only (the votes :func:`graphs.vote_matrix`
    keeps). The party is the one on each vote record, so a deputy who switched
    parties mid-month is held to the right party on each side of the switch.

    Columns: ``deputado_id, nome, partido, uf, n_votes`` (contested Sim/Não
    votes cast), ``n_party`` (of those, with a party orientation to follow),
    ``n_with_party``, ``with_party`` (share), ``n_free`` (the party freed its
    members), ``n_none`` (the deputy's party, federation or bloc is listed but
    gave no orientation), ``n_unknown`` (the deputy's party matches no
    published bancada, e.g. a bloc whose name was cut off), ``n_gov``,
    ``n_with_gov``, ``with_gov``.
    """
    d = g.load_month(month, data_dir)
    _, kept, _ = g.vote_matrix(d.votes, lop=lop, obstruction_as_no=obstruction_as_no)
    v = d.votes[d.votes.votacao_id.isin(set(kept))].copy()
    v["s"] = _sign(v.voto, obstruction_as_no)
    v = v[v.s.notna()]
    v["party"] = v.partido.map(party_key)

    a = applicable(d.orientations)
    listed = _expand(d.orientations)[["votacao_id", "party"]].drop_duplicates().assign(listed=True)
    v = v.merge(a[["votacao_id", "party", "orientacao"]], on=["votacao_id", "party"], how="left")
    v = v.merge(listed, on=["votacao_id", "party"], how="left")
    v["listed"] = v.listed.notna()
    po = _sign(v.orientacao, obstruction_as_no)
    v["free"] = v.orientacao == FREE
    v["none"] = v.orientacao.isna() & v.listed
    v["unknown"] = v.orientacao.isna() & ~v.listed
    v["followed"] = po.notna()
    v["with_party"] = v.followed & (po == v.s)

    go = _sign(v.votacao_id.map(leadership(d.orientations, "governo")), obstruction_as_no)
    v["gov"] = go.notna()
    v["with_gov"] = v.gov & (go == v.s)

    out = v.groupby("deputado_id").agg(
        n_votes=("s", "size"), n_party=("followed", "sum"), n_with_party=("with_party", "sum"),
        n_free=("free", "sum"), n_none=("none", "sum"), n_unknown=("unknown", "sum"), n_gov=("gov", "sum"), n_with_gov=("with_gov", "sum"),
    ).astype("int64")
    with np.errstate(invalid="ignore", divide="ignore"):
        out["with_party"] = (out.n_with_party / out.n_party).round(4)
        out["with_gov"] = (out.n_with_gov / out.n_gov).round(4)
    info = d.deputies.set_index("deputado_id")[["nome", "partido", "uf"]]
    out = info.reindex(out.index).join(out)
    cols = ["nome", "partido", "uf", "n_votes", "n_party", "n_with_party", "with_party", "n_free",
            "n_none", "n_unknown", "n_gov", "n_with_gov", "with_gov"]
    return out[cols].reset_index()
