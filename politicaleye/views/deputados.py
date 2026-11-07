"""One row per deputy of a legislature, across sources: ``data/views/deputados_<leg>.csv``.

Joins, through ``data/ref/politicians.csv``:

- the Câmara: votes cast and discipline (with party, government and party
  majority), pooled over every month of the legislature;
- the Portal da Transparência: the amendments the deputy authored for the
  budgets that legislature approved;
- TSE: the campaign that elected them.

``methodology/views.md`` explains every column.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from ..camara import graphs as cg
from ..camara import orientations as co
from ..io import write_csv

COLS = ["pessoa", "deputado_id", "nome", "partido", "uf", "meses", "n_votes", "n_party", "with_party", "n_gov",
        "with_gov", "n_majority", "with_majority", "emendas", "emendas_empenhado", "emendas_pago",
        "campanha_sq_candidato", "campanha_resultado", "campanha_total", "campanha_partido", "campanha_fefc",
        "campanha_proprios", "campanha_doadores_pf"]


def _log(msg: str) -> None:
    print(f"[views] {msg}", file=sys.stderr)


def election_of(leg: int) -> int:
    """The general election that chose legislature ``leg`` (held the October before it began)."""
    return 1795 + 4 * leg - 1


def budget_years(leg: int) -> list[int]:
    """Budgets a legislature votes on: each year's budget is approved the year before."""
    start = 1795 + 4 * leg
    return [start + 1, start + 2, start + 3, start + 4]


def _money(s: pd.Series) -> pd.Series:
    return (pd.to_numeric(s, errors="coerce").fillna(0) * 100).round().astype("int64")


def _reais(c: pd.Series) -> pd.Series:
    return (c // 100).astype(str) + "." + (c % 100).astype(str).str.zfill(2)


def build(leg: int, data: Path) -> pd.DataFrame:
    months = [m for m in cg.months(data / "camara") if cg.legislatura(m) == leg]
    rows, people = [], []
    for m in months:
        d = co.discipline(m, data_dir=data / "camara")
        if len(d):
            rows.append(d.assign(month=m))
        people.append(cg.load_month(m, data / "camara").deputies.assign(month=m))
    disc = pd.concat(rows, ignore_index=True)
    sums = disc.groupby("deputado_id")[["n_votes", "n_party", "n_with_party", "n_gov", "n_with_gov", "n_majority",
                                         "n_with_majority"]].sum()
    for a, n in (("with_party", "n_party"), ("with_gov", "n_gov"), ("with_majority", "n_majority")):
        sums[a] = (sums[f"n_{a}"] / sums[n]).where(sums[n] > 0).round(4)
    ppl = pd.concat(people, ignore_index=True).sort_values("month")
    last = ppl.groupby("deputado_id").agg(nome=("nome", "last"), partido=("partido", "last"), uf=("uf", "last"),
                                          meses=("month", "nunique"))
    # Deputies of the legislature: those who cast a contested vote in it (the
    # Câmara's authorship records also carry senators who have a deputy id).
    out = last.join(sums, how="inner").reset_index()
    out["deputado_id"] = out.deputado_id.astype(str)

    x = pd.read_csv(data / "ref" / "politicians.csv", dtype=str, keep_default_na=False)
    pessoa = x[x.fonte == "camara"].set_index("id").pessoa
    out["pessoa"] = out.deputado_id.map(pessoa).fillna("camara:" + out.deputado_id)

    # Amendments for the budgets this legislature approved, by every author code of the person.
    au = pd.read_csv(data / "emendas" / "por_autor.csv", dtype=str, keep_default_na=False)
    au = au[au.ano.astype(int).isin(budget_years(leg))]
    au["pessoa"] = au.autor_codigo.map(x[x.fonte == "emendas"].set_index("id").pessoa)
    em = au.dropna(subset=["pessoa"]).assign(e=lambda t: _money(t.empenhado), p=lambda t: _money(t.pago),
                                             n=lambda t: t.emendas.astype(int))
    em = em.groupby("pessoa").agg(emendas=("n", "sum"), emendas_empenhado=("e", "sum"), emendas_pago=("p", "sum"))
    out = out.merge(em, left_on="pessoa", right_index=True, how="left")
    for c in ("emendas", "emendas_empenhado", "emendas_pago"):
        out[c] = out[c].fillna(0).astype("int64")

    # The campaign that elected them: their federal-deputy candidacy in that election.
    y = election_of(leg)
    tdir = data / "tse" / str(y)
    if tdir.exists():
        cand = pd.read_csv(tdir / "candidatos.csv", dtype=str, keep_default_na=False)
        cand = cand[cand.cargo == "Deputado Federal"].set_index("sq_candidato")
        rec = pd.read_csv(tdir / "receitas_por_candidato.csv", dtype=str, keep_default_na=False).set_index("sq_candidato")
        t = x[(x.fonte == "tse") & x.id.isin(cand.index)][["pessoa", "id"]].drop_duplicates("pessoa")
        t = t.join(cand[["resultado"]], on="id").join(
            rec[["total", "origem_partido", "fonte_fefc", "origem_proprios", "n_doadores_pf"]], on="id")
        t.columns = ["pessoa", "campanha_sq_candidato", "campanha_resultado", "campanha_total", "campanha_partido",
                     "campanha_fefc", "campanha_proprios", "campanha_doadores_pf"]
        out = out.merge(t, on="pessoa", how="left")
    for c in COLS:
        if c not in out:
            out[c] = ""
    out = out.astype(object).where(out.notna(), "")   # empty, not NaN, in every column
    for c in ("emendas_empenhado", "emendas_pago"):
        out[c] = _reais(out[c].astype("int64"))
    for c in ("meses", "n_votes", "n_party", "n_gov", "n_majority"):
        out[c] = out[c].map(lambda v: "" if v == "" else str(int(v)))
    out = out.assign(_k=pd.to_numeric(out.deputado_id)).sort_values("_k").drop(columns="_k")[COLS]
    write_csv(out, data / "views" / f"deputados_{leg}.csv")
    linked = (out.campanha_sq_candidato != "").mean()
    _log(f"deputados_{leg}: {len(out)} deputies, {linked:.0%} with their campaign, "
         f"{(out.emendas.astype(int) > 0).mean():.0%} with amendments")
    return out
