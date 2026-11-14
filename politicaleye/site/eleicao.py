"""Summaries for the election tab of the deputies page: ``data/site/eleicao/``.

What the general election held at the end of a legislature did to its deputies, and the Chamber it chose
(the 57th legislature and the 2026 election; the 56th and 2022):

    deputados_<leg>.csv  one row per deputy of the legislature (data/site/deputados): whether they ran in that
                         election, for which office and with what result, what their campaign raised, and the
                         measures the tab compares the outcomes on: the ranking's index with its default
                         weights, roll-call participation, amendment money paid, and the share and amount of
                         it paid to towns whose mayor was of their party
    eleitos_<year>.csv   one row per federal deputy elected that year: party, federation, state, result, money
                         raised, and whether they sat in the outgoing legislature, in an earlier one, or never
    partidos_<year>.csv  seats per party: won at the election before, held by the deputies sitting in the
                         election month, and won at this one (re-elected, back after a break, new)
    resumo.json          per legislature: the election, how many deputies had each outcome, seats known

Candidacies are tied to deputies through the politician crosswalk (data/ref/politicians.csv), which links a
deputy to a candidacy for any office, so one who ran for the Senate or a governorship is not counted as
having stayed out. No CPF is used. See methodology/views.md.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..views.deputados import election_of
from .common import csv, write_json
from .deputados import party_in

LEGS = (57, 56)
FEDERAL = "Deputado Federal"
# The outcome of each deputy of the legislature at the election that ended it.
GROUPS = ("reeleito", "nao_reeleito", "outro_eleito", "outro_derrotado", "sem_resultado", "nao_concorreu")
# Seats per state in the Câmara (fixed since 1994): a state with fewer elected than this is still being counted.
SEATS = {"SP": 70, "MG": 53, "RJ": 46, "BA": 39, "RS": 31, "PR": 30, "PE": 25, "CE": 22, "MA": 18, "GO": 17, "PA": 17, "SC": 16,
         "PB": 12, "ES": 10, "PI": 10, "AL": 9, "AC": 8, "AM": 8, "AP": 8, "DF": 8, "MS": 8, "MT": 8, "RN": 8, "RO": 8, "RR": 8,
         "SE": 8, "TO": 8}
# The ranking page's default (balanced) weights, and the Speakers whose participation it leaves out (docs/ranking/app.js).
WEIGHTS = {"presenca": 3, "projetos_autor": 2, "relatorias": 2, "economia": 3}
SPEAKERS = {56: {"74693", "160541"}, 57: {"160541", "160674"}}
MIN_MONTHS = 12   # deputies the ranking scores, and the tab compares


def _read(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame()


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _pctile(pool: np.ndarray, v: float) -> float:
    """Percentile rank (0-100) of v among pool, ties sharing the middle, as the ranking page computes it."""
    if np.isnan(v) or not len(pool):
        return np.nan
    return 100 * ((pool < v).sum() + (pool == v).sum() / 2) / len(pool)


def ranking_index(r: pd.DataFrame, leg: int) -> pd.Series:
    """The ranking page's score with its default weights, for deputies with 12 months or more (else NaN).

    ``r`` is ``data/site/ranking/deputados_<leg>.csv``. Each criterion is the deputy's percentile among the
    ranked deputies (the allowance against their state's, reversed); the score is the weighted mean of the
    criteria they have data for.
    """
    r = r.copy()
    for c in ("meses", "presenca", "projetos_autor", "relatorias", "cota_mes"):
        r[c] = _num(r[c]) if c in r else np.nan
    ranked = r.meses >= MIN_MONTHS
    speaker = r.deputado_id.isin(SPEAKERS.get(leg, set()))
    scores = pd.DataFrame(index=r.index)
    for k in ("presenca", "projetos_autor", "relatorias"):
        out = speaker if k == "presenca" else pd.Series(False, index=r.index)
        pool = r.loc[ranked & r[k].notna() & ~out, k].to_numpy()
        scores[k] = [np.nan if o else _pctile(pool, v) for v, o in zip(r[k], out)]
    spend = ranked & (r.cota_mes > 0)
    pools = {uf: g.to_numpy() for uf, g in r[spend].groupby("uf").cota_mes}
    scores["economia"] = [100 - _pctile(pools[u], v) if v > 0 and len(pools.get(u, ())) >= 3 else np.nan
                          for v, u in zip(r.cota_mes.fillna(0), r.uf)]
    w = pd.Series(WEIGHTS)
    have = scores[w.index].notna()
    total = (scores[w.index].fillna(0) * w).sum(axis=1)
    weight = (have * w).sum(axis=1)
    return (total / weight).where(ranked & (weight > 0)).round(2)


def _candidacies(data: Path, year: int) -> pd.DataFrame:
    """Every candidacy of the election with the person the crosswalk ties it to, and its money raised."""
    c = _read(data / "tse" / str(year) / "candidatos.csv")
    rec = _read(data / "tse" / str(year) / "receitas_por_candidato.csv")
    x = _read(data / "ref" / "politicians.csv")
    if not len(c):
        return pd.DataFrame()
    who = x[x.fonte == "tse"].drop_duplicates("id").set_index("id").pessoa if len(x) else pd.Series(dtype=str)
    c["pessoa"] = c.sq_candidato.map(who).fillna("")
    c["campanha_total"] = c.sq_candidato.map(_num(rec.set_index("sq_candidato").total)) if len(rec) else np.nan
    c["eleito"] = c.resultado.str.startswith("ELEITO")
    return c


def _pick(c: pd.DataFrame) -> pd.DataFrame:
    """One candidacy per person: one with a result before one without, a win before a loss, the Câmara first.

    A deputy who registered for the Câmara and then ran for the Senate has two candidacies; the one that went
    to the ballot is theirs."""
    c = c[c.pessoa != ""].assign(_r=lambda t: t.resultado == "", _e=lambda t: ~t.eleito, _f=lambda t: t.cargo != FEDERAL)
    return c.sort_values(["pessoa", "_r", "_e", "_f", "sq_candidato"]).drop_duplicates("pessoa").drop(columns=["_r", "_e", "_f"])


def outcome(cargo: str, resultado: str) -> str:
    if not cargo:
        return "nao_concorreu"
    if not resultado:
        return "sem_resultado"
    won = resultado.startswith("ELEITO")
    if cargo == FEDERAL:
        return "reeleito" if won else "nao_reeleito"
    return "outro_eleito" if won else "outro_derrotado"


def _sitting(data: Path, year: int, leg: int) -> tuple[str, pd.DataFrame]:
    """The deputies in the Câmara's tables in the election month (October), or the latest month before it."""
    from ..camara import graphs as g
    months = [f.stem for f in sorted((data / "camara" / "deputies").glob("*.csv"))
              if f.stem <= f"{year}-10" and g.legislatura(f.stem) == leg]
    if not months:
        return "", pd.DataFrame(columns=["deputado_id", "partido", "uf"])
    m = months[-1]
    sit = pd.read_csv(data / "camara" / "deputies" / f"{m}.csv", dtype=str, keep_default_na=False)
    # Former deputies credited as authors of a paper appear with no party or state: they do not sit.
    return m, sit[(sit.partido != "") | (sit.uf != "")]


def _first_legislature(data: Path, x: pd.DataFrame) -> pd.Series:
    """The first legislature each person appears in the Câmara's monthly tables (which start in 2015)."""
    from ..camara import graphs as g
    seen: dict[str, int] = {}
    for f in sorted((data / "camara" / "deputies").glob("*.csv")):
        leg = g.legislatura(f.stem)
        for i in pd.read_csv(f, dtype=str, usecols=["deputado_id"]).deputado_id:
            seen.setdefault(i, leg)
    who = x[x.fonte == "camara"].set_index("id").pessoa
    t = pd.Series(seen, dtype=int)
    return t.groupby(t.index.map(who)).min() if len(t) else pd.Series(dtype=int)


def build_leg(data: Path, leg: int) -> dict:
    out = data / "site" / "eleicao"
    year = election_of(leg + 1)
    v = _read(data / "site" / "deputados" / f"deputados_{leg}.csv")
    c = _candidacies(data, year)
    if not len(v) or not len(c):
        return {}

    # Each deputy of the legislature: the candidacy that went to the ballot, and its result.
    measures = ["presenca", "emendas_pago", "prefeito_mesmo_partido", "prefeito_base", "prefeito_mesmo_partido_valor"]
    d = v[["pessoa", "deputado_id", "nome", "partido", "uf", "meses"]].copy()
    for k in measures:
        d[k] = _num(v[k]) if k in v else np.nan
    mine = _pick(c[c.pessoa.isin(set(v.pessoa))])
    d = d.merge(mine[["pessoa", "sq_candidato", "cargo", "uf", "nome_urna", "partido", "federacao", "resultado", "genero", "campanha_total"]].rename(
        columns={"uf": "candidatura_uf", "partido": "candidatura_partido"}), on="pessoa", how="left")
    for k in ("sq_candidato", "cargo", "candidatura_uf", "nome_urna", "candidatura_partido", "federacao", "resultado", "genero"):
        d[k] = d[k].fillna("")
    d["grupo"] = [outcome(a, b) for a, b in zip(d.cargo, d.resultado)]
    # The party they ran under, or their last party in the Câmara if they did not run; one name per party.
    d["partido_eleicao"] = [party_in(p or q, year) for p, q in zip(d.candidatura_partido, d.partido)]

    # What the tab compares the outcomes on: the ranking's index, and the Speaker's participation left out.
    d.loc[d.deputado_id.isin(SPEAKERS.get(leg, set())), "presenca"] = np.nan
    rk = _read(data / "site" / "ranking" / f"deputados_{leg}.csv")
    d["indice"] = d.deputado_id.map(rk.assign(i=ranking_index(rk, leg)).set_index("deputado_id").i) if len(rk) else np.nan
    d["meses"] = _num(d.meses).astype("Int64")
    cols = ["pessoa", "deputado_id", "nome", "partido", "uf", "meses", "grupo", "cargo", "resultado", "candidatura_partido",
            "candidatura_uf", "federacao", "nome_urna", "genero", "sq_candidato", "partido_eleicao", "campanha_total", "indice", "presenca",
            "emendas_pago", "prefeito_mesmo_partido", "prefeito_base", "prefeito_mesmo_partido_valor"]
    d = d[cols].sort_values("deputado_id", key=lambda s: s.astype(int))
    csv(d.round({"campanha_total": 2, "presenca": 4, "emendas_pago": 2, "prefeito_mesmo_partido": 4, "prefeito_base": 4,
                 "prefeito_mesmo_partido_valor": 2}), out / f"deputados_{leg}.csv")

    # The Chamber the election chose: each federal deputy elected, and whether they had sat in the Câmara.
    # New: no Câmara id, or one they got only when the next legislature began (2022's newcomers have one now).
    x = _read(data / "ref" / "politicians.csv")
    first = _first_legislature(data, x)
    has_id = set(x[x.fonte == "camara"].pessoa)
    el = c[(c.cargo == FEDERAL) & c.eleito].copy()
    new = ~el.pessoa.isin(has_id) | (el.pessoa.map(first) > leg)
    el["origem"] = np.where(el.pessoa.isin(set(v.pessoa)), "reeleito", np.where(new, "novo", "ex_deputado"))
    el["deputado_id"] = el.pessoa.map(x[x.fonte == "camara"].drop_duplicates("pessoa").set_index("pessoa").id).fillna("")
    el["partido_key"] = [party_in(p, year) for p in el.partido]
    el = el[["sq_candidato", "nome_urna", "partido", "partido_key", "federacao", "uf", "resultado", "origem", "deputado_id", "campanha_total"]]
    csv(el.round({"campanha_total": 2}).sort_values(["uf", "partido_key", "nome_urna", "sq_candidato"]), out / f"eleitos_{year}.csv")

    # Seats per party: at the election before, sitting in the election month, and won now.
    prev = _read(data / "tse" / str(year - 4) / "candidatos.csv")
    prev = prev[(prev.cargo == FEDERAL) & prev.resultado.str.startswith("ELEITO")] if len(prev) else pd.DataFrame(columns=["partido"])
    month, sit = _sitting(data, year, leg)
    parts = pd.DataFrame({
        "eleitos_antes": pd.Series([party_in(p, year) for p in prev.partido], dtype=str).value_counts(),
        "em_exercicio": pd.Series([party_in(p, year) for p in sit.partido], dtype=str).value_counts(),
        "eleitos": el.partido_key.value_counts(),
        **{o: el[el.origem == o].partido_key.value_counts() for o in ("reeleito", "ex_deputado", "novo")},
    }).fillna(0).astype(int).rename_axis("partido").reset_index()
    parts = parts.sort_values(["eleitos", "em_exercicio", "partido"], ascending=[False, False, True])
    csv(parts, out / f"partidos_{year}.csv")

    won = el.uf.value_counts()
    pending = sorted(u for u, n in SEATS.items() if won.get(u, 0) < n)
    ran = d[d.grupo.isin(["reeleito", "nao_reeleito"])]
    return {
        "eleicao": year, "anterior": year - 4, "legislatura_seguinte": leg + 1, "deputados": len(d),
        "grupos": {g: int((d.grupo == g).sum()) for g in GROUPS},
        "grupos_12_meses": {g: int(((d.grupo == g) & (d.meses >= MIN_MONTHS)).sum()) for g in GROUPS},
        "concorreram_camara": len(ran), "taxa_reeleicao": round(float((ran.grupo == "reeleito").mean()), 4) if len(ran) else None,
        "cadeiras": sum(SEATS.values()), "eleitos": len(el), "ufs_pendentes": pending, "cadeiras_pendentes": sum(SEATS[u] - won.get(u, 0) for u in pending),
        "origem": {o: int((el.origem == o).sum()) for o in ("reeleito", "ex_deputado", "novo")},
        "em_exercicio_mes": month, "em_exercicio": len(sit), "eleitos_antes": len(prev),
    }


def build(data: Path) -> dict:
    out = {leg: build_leg(data, leg) for leg in LEGS}
    out = {k: v for k, v in out.items() if v}
    write_json({"legislaturas": sorted(out, reverse=True), "builds": out}, data / "site" / "eleicao" / "resumo.json")
    return out
