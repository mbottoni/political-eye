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

from . import blocos as b
from . import graphs as g

# Orientations a deputy can follow or defy. "Liberado" frees the members; an
# empty orientation means the bancada gave none (seen from 2021 on).
FREE = "Liberado"
NO_PARTY = "S.PART."   # sem partido: no party to follow or to be a majority of
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


def _elements(toks: list[str]) -> list[frozenset[str]]:
    """The parties and federations of a parsed bloc name, in order.

    ``Fdr`` plus a party is that party's federation; the federation's other
    parties may follow (``FdrPsdbCid``) and are part of the same element.
    """
    out: list[frozenset[str]] = []
    fed = False
    for t in toks:
        if t == FEDERATION_MARK:
            fed = True
            continue
        k = party_key(TOKENS[t])
        if fed:
            out.append(frozenset(FEDERATIONS.get(k, (k,))))
        elif not (out and len(out[-1]) > 1 and k in out[-1]):
            out.append(frozenset({k}))
        fed = False
    return out


@lru_cache(maxsize=None)
def bloc_elements(name: str) -> tuple[frozenset[str], ...] | None:
    """The ordered elements of a bloc name as published, or None if it is not a bloc that parses."""
    bloc_prefix = name.startswith("Bl ")
    body = (name[3:] if bloc_prefix else name).rstrip(".")
    toks = _tokens(body)
    if toks is None or not (bloc_prefix or len(toks) >= 2):
        return None
    return tuple(_elements(toks))


@lru_cache(maxsize=None)
def decode(name: str) -> Bancada:
    """What a published bancada name means."""
    if name in LEADERSHIPS:
        return Bancada(name, "leadership", frozenset(), True, LEADERSHIPS[name])
    if name.startswith("Fdr "):
        return Bancada(name, "federation", frozenset(party_key(p) for p in name[4:].split("-")))
    els = bloc_elements(name)
    if els is not None:
        return Bancada(name, "bloc", frozenset().union(*els), complete=not name.endswith("..."))
    if name.startswith("Bl ") or name == "Bloco Parlamentar":
        return Bancada(name, "bloc", frozenset(), complete=False)
    return Bancada(name, "party", frozenset({party_key(name)}))


# ------------------------------------------------------- cut-off bloc names

def _api_elements(nome: str, legislatura: str, blocos: pd.DataFrame, members: pd.DataFrame) -> list[frozenset[str]]:
    """The ordered elements of a bloc name in the blocs API ("UNIÃO, PP, Federação PSDB CIDADANIA")."""
    out = []
    for e in b.name_elements(nome):
        if e.startswith("Federação"):
            ids = blocos[(blocos.legislatura == legislatura) & (blocos.federacao == "1") & (blocos.nome == e)].bloco_id
            out.append(frozenset(party_key(p) for p in members[members.bloco_id.isin(set(ids))].partido))
        else:
            out.append(frozenset({party_key(e)}))
    return out


def _starts_with(full: list[frozenset[str]], head: tuple[frozenset[str], ...]) -> bool:
    # The last element of a cut-off name may itself be cut ("FdrPsdb" for the
    # PSDB-Cidadania federation): it only needs to be part of the API's.
    n = len(head)
    return (0 < n <= len(full) and all(full[i] == head[i] for i in range(n - 1))
            and head[-1] <= full[n - 1])


def completions(
    orientations: pd.DataFrame, votacoes: pd.DataFrame, legislatura: int, root,
    *, before_recording: bool = False,
) -> dict[tuple[str, str], frozenset[str]]:
    """Full membership of cut-off bloc names, from the recorded blocs API.

    A cut-off name (``Bl UniPpPsd...``) is completed when exactly one
    recorded bloc of the same legislature, listed on the day of the votação,
    has a name that starts with the same parties in the same order and
    members that include them. Returns ``{(votacao_id, bancada): members}``.
    See :func:`blocos.in_effect` for which days a recorded row covers.
    """
    blocos, members = b.load(root)
    cut = orientations[orientations.bancada.str.endswith("...")]
    if cut.empty or blocos.empty:
        return {}
    leg = str(legislatura)
    day = votacoes.set_index("id").data
    out = {}
    for vid, name in cut[["votacao_id", "bancada"]].drop_duplicates().itertuples(index=False, name=None):
        head = bloc_elements(name)
        if not head or vid not in day.index:
            continue
        on = day[vid]
        bl = b.in_effect(blocos[(blocos.legislatura == leg) & (blocos.federacao == "0")], on,
                         before_recording=before_recording)
        hits = [r.bloco_id for r in bl.itertuples() if _starts_with(_api_elements(r.nome, leg, blocos, members), head)]
        if len(hits) != 1:
            continue
        mem = b.in_effect(members[members.bloco_id == hits[0]], on, before_recording=before_recording)
        got = frozenset(party_key(p) for p in mem.partido)
        if got >= decode(name).members:
            out[(vid, name)] = got
    return out


def _expand(orientations: pd.DataFrame, completed: dict | None = None) -> pd.DataFrame:
    """One row per (votação, member party) of every party, federation and bloc row.

    ``completed`` maps ``(votacao_id, bancada)`` to the full members of a
    cut-off bloc name (see :func:`completions`).
    """
    completed = completed or {}
    rows = []
    for vid, name, ori in orientations[["votacao_id", "bancada", "orientacao"]].itertuples(index=False, name=None):
        bc = decode(name)
        if bc.kind != "leadership":
            rows.extend((vid, p, bc.kind, ori) for p in completed.get((vid, name), bc.members))
    return pd.DataFrame(rows, columns=["votacao_id", "party", "level", "orientacao"]).drop_duplicates()


def applicable(orientations: pd.DataFrame, completed: dict | None = None) -> pd.DataFrame:
    """The orientation each party was given in each votação.

    A party's own orientation counts first, then its federation's, then its
    bloc's. An empty orientation passes to the next level; "Liberado" does
    not (the members were freed). If two bancadas at the same level disagree
    for a party, that party has no applicable orientation in that votação.

    Columns: ``votacao_id, party, level, orientacao`` (``party`` is a
    :func:`party_key`; ``level`` is party, federation or bloc).
    ``completed``: see :func:`completions`.
    """
    cols = ["votacao_id", "party", "level", "orientacao"]
    a = _expand(orientations[orientations.orientacao != ""], completed)
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


def discipline(
    month: str, *, lop: float = g.LOP, obstruction_as_no: bool = True, blocs: str | None = "recorded",
    data_dir=None,
) -> pd.DataFrame:
    """How often each deputy voted with their party, the government and their party's majority.

    Counts contested Plenário votes only (the votes :func:`graphs.vote_matrix`
    keeps). The party is the one on each vote record, so a deputy who switched
    parties mid-month is held to the right party on each side of the switch.

    ``blocs`` completes cut-off bloc names from the recorded blocs API
    (:func:`completions`): ``"recorded"`` only on days the record covers,
    ``"listed"`` also before recording started (assumes each bloc already
    listed then had the same members all along), ``None`` never.

    Columns: ``deputado_id, nome, partido, uf, n_votes`` (contested Sim/Não
    votes cast), ``n_party`` (of those, with a party orientation to follow),
    ``n_with_party``, ``with_party`` (share), ``n_free`` (the party freed its
    members), ``n_none`` (the deputy's party, federation or bloc is listed but
    gave no orientation, or the deputy has no party), ``n_unknown`` (the
    deputy's party matches no published bancada, e.g. a bloc whose name was
    cut off), ``n_gov``, ``n_with_gov``, ``with_gov``, ``n_majority`` (votes
    where the other deputies of the party who voted had a majority side),
    ``n_with_majority``, ``with_majority``.
    """
    if blocs not in ("recorded", "listed", None):
        raise ValueError(f"blocs must be 'recorded', 'listed' or None, not {blocs!r}")
    d = g.load_month(month, data_dir)
    _, kept, _ = g.vote_matrix(d.votes, lop=lop, obstruction_as_no=obstruction_as_no)
    v = d.votes[d.votes.votacao_id.isin(set(kept))].copy()
    v["s"] = _sign(v.voto, obstruction_as_no)
    v = v[v.s.notna()]
    v["party"] = v.partido.map(party_key)
    no_party = v.partido == NO_PARTY

    done = {} if blocs is None else completions(
        d.orientations, d.votacoes, g.legislatura(month), g._root(data_dir), before_recording=blocs == "listed")
    a = applicable(d.orientations, done)
    listed = _expand(d.orientations, done)[["votacao_id", "party"]].drop_duplicates().assign(listed=True)
    v = v.merge(a[["votacao_id", "party", "orientacao"]], on=["votacao_id", "party"], how="left")
    v = v.merge(listed, on=["votacao_id", "party"], how="left")
    v["listed"] = v.listed.notna()
    v.loc[no_party.to_numpy(), "orientacao"] = np.nan
    po = _sign(v.orientacao, obstruction_as_no)
    v["free"] = v.orientacao == FREE
    v["none"] = v.orientacao.isna() & (v.listed | no_party.to_numpy())
    v["unknown"] = v.orientacao.isna() & ~v.listed & ~no_party.to_numpy()
    v["followed"] = po.notna()
    v["with_party"] = v.followed & (po == v.s)

    go = _sign(v.votacao_id.map(leadership(d.orientations, "governo")), obstruction_as_no)
    v["gov"] = go.notna()
    v["with_gov"] = v.gov & (go == v.s)

    # The majority of the *other* deputies of the same party who voted: a
    # deputy's own vote never makes the majority they are measured against.
    yes, no = (v.s == 1).astype(int), (v.s == -1).astype(int)
    grp = [v.votacao_id, v.party]
    others = (yes.groupby(grp).transform("sum") - yes) - (no.groupby(grp).transform("sum") - no)
    side = np.sign(others).where(~no_party.to_numpy(), 0)
    v["majority"] = side != 0
    v["with_majority"] = v.majority & (side == v.s)

    out = v.groupby("deputado_id").agg(
        n_votes=("s", "size"), n_party=("followed", "sum"), n_with_party=("with_party", "sum"),
        n_free=("free", "sum"), n_none=("none", "sum"), n_unknown=("unknown", "sum"), n_gov=("gov", "sum"),
        n_with_gov=("with_gov", "sum"), n_majority=("majority", "sum"), n_with_majority=("with_majority", "sum"),
    ).astype("int64")
    with np.errstate(invalid="ignore", divide="ignore"):
        out["with_party"] = (out.n_with_party / out.n_party).round(4)
        out["with_gov"] = (out.n_with_gov / out.n_gov).round(4)
        out["with_majority"] = (out.n_with_majority / out.n_majority).round(4)
    info = d.deputies.set_index("deputado_id")[["nome", "partido", "uf"]]
    out = info.reindex(out.index).join(out)
    cols = ["nome", "partido", "uf", "n_votes", "n_party", "n_with_party", "with_party", "n_free",
            "n_none", "n_unknown", "n_gov", "n_with_gov", "with_gov", "n_majority", "n_with_majority",
            "with_majority"]
    return out[cols].reset_index()
