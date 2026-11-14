"""One row per senator of a legislature, across sources: ``data/views/senadores_<leg>.csv``.

The senators' counterpart of ``deputados.py``. Joins, through ``data/ref/politicians.csv``:

- the Senado: votes cast and discipline (with party, government and party
  majority), pooled over every month of the legislature;
- the Portal da Transparência: the amendments the senator authored for the
  budgets that legislature approved;
- TSE: the Senate race that gave them the seat they held (as senator or
  suplente). A senator's eight-year term spans two legislatures, so for the
  57th that is the 2022 or the 2018 election.

``methodology/views.md`` explains every column.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from ..io import write_csv
from ..senado import graphs as sg
from ..senado import orientations as so
from .deputados import _money, _reais, budget_years, election_of

COLS = ["pessoa", "senador_id", "nome", "partido", "uf", "meses", "n_votes", "n_party", "with_party", "n_gov",
        "with_gov", "n_majority", "with_majority", "emendas", "emendas_empenhado", "emendas_pago",
        "campanha_ano", "campanha_cargo", "campanha_sq_candidato", "campanha_resultado", "campanha_total",
        "campanha_partido", "campanha_fefc", "campanha_proprios", "campanha_doadores_pf"]
RACES = ("Senador", "1º Suplente", "2º Suplente")   # TSE's cargo for the three names on a Senate slate


def _log(msg: str) -> None:
    print(f"[views] {msg}", file=sys.stderr)


def seat_elections(leg: int) -> list[int]:
    """Elections whose senators sit in legislature ``leg``: the one that chose it and the one before (8-year terms)."""
    return [election_of(leg) - 4, election_of(leg)]


def campaigns(data: Path, x: pd.DataFrame, years, cargos=RACES) -> pd.DataFrame:
    """Every candidacy the crosswalk ``x`` links to a person in ``years`` (only for ``cargos``; None for any), with its money."""
    t = x[x.fonte == "tse"][["pessoa", "id"]]
    money = ["total", "origem_partido", "fonte_fefc", "origem_proprios", "n_doadores_pf"]
    out = []
    for y in years:
        d = data / "tse" / str(y)
        if not (d / "candidatos.csv").exists():
            continue
        c = pd.read_csv(d / "candidatos.csv", dtype=str, keep_default_na=False)
        if cargos is not None:
            c = c[c.cargo.isin(cargos)]
        c = c.set_index("sq_candidato")[["cargo", "uf", "numero", "partido", "resultado"]]
        rec = pd.read_csv(d / "receitas_por_candidato.csv", dtype=str, keep_default_na=False).set_index("sq_candidato")
        r = t[t.id.isin(c.index)].join(c, on="id").join(rec[money], on="id")
        out.append(r.assign(ano=str(y)))
    cols = ["pessoa", "sq_candidato", "ano", "cargo", "uf", "numero", "partido", "resultado", *money]
    if not out:
        return pd.DataFrame(columns=cols)
    return pd.concat(out, ignore_index=True).rename(columns={"id": "sq_candidato"})[cols].fillna("")


def build(leg: int, data: Path) -> pd.DataFrame:
    root = data / "senado"
    months = [m for m in sg.months(root) if sg.legislatura(m) == leg]
    rows, people = [], []
    for m in months:
        d = so.discipline(m, window=1, data_dir=root)   # one month at a time, then summed: the votes are the same
        if len(d):
            rows.append(d)
        people.append(sg.load_month(m, root).senators.assign(month=m))
    cols = ["n_votes", "n_party", "n_with_party", "n_gov", "n_with_gov", "n_majority", "n_with_majority"]
    disc = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=[sg.MEMBER, *cols])
    sums = disc.groupby(sg.MEMBER)[cols].sum()
    for a, n in (("with_party", "n_party"), ("with_gov", "n_gov"), ("with_majority", "n_majority")):
        sums[a] = (sums[f"n_{a}"] / sums[n]).where(sums[n] > 0).round(4)
    ppl = pd.concat(people, ignore_index=True).sort_values("month")
    # Senators of the legislature: those in office at one of its roll calls (each roll call lists all 81 seats,
    # absences included). A senator seen only through a signature is not one.
    sitting = set(ppl.loc[ppl.n_votes > 0, sg.MEMBER])
    ppl = ppl[ppl[sg.MEMBER].isin(sitting)]
    named = ppl.assign(partido=ppl.partido.where(ppl.partido != "", None))
    last = named.groupby(sg.MEMBER).agg(nome=("nome", "last"), partido=("partido", "last"), uf=("uf", "last"),
                                        meses=("month", "nunique"))
    out = last.join(sums[["n_votes", "n_party", "with_party", "n_gov", "with_gov", "n_majority", "with_majority"]]).reset_index()
    out["senador_id"] = out[sg.MEMBER].astype(str)
    out["partido"] = out.partido.fillna("")
    out["n_votes"] = out.n_votes.fillna(0)

    x = pd.read_csv(data / "ref" / "politicians.csv", dtype=str, keep_default_na=False)
    pessoa = x[x.fonte == "senado"].set_index("id").pessoa
    out["pessoa"] = out.senador_id.map(pessoa).fillna("senado:" + out.senador_id)

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

    # The race that gave them their seat: a Senate candidacy in one of the two elections whose senators sit in
    # this legislature, the one they won if they ran in both (a suplente who later won a seat of their own).
    races = campaigns(data, x, seat_elections(leg))
    races = races[races.pessoa.isin(set(out.pessoa))]
    won = races.resultado.str.startswith("ELEITO")
    seat = (races.assign(_w=won, _y=races.ano).sort_values(["pessoa", "_w", "_y"]).groupby("pessoa").tail(1)
            .drop(columns=["_w", "_y", "uf", "numero", "partido"]))
    seat = seat.rename(columns={"sq_candidato": "campanha_sq_candidato", "cargo": "campanha_cargo", "resultado": "campanha_resultado",
                                "total": "campanha_total", "origem_partido": "campanha_partido", "fonte_fefc": "campanha_fefc",
                                "origem_proprios": "campanha_proprios", "n_doadores_pf": "campanha_doadores_pf",
                                "ano": "campanha_ano"})
    out = out.merge(seat, on="pessoa", how="left")
    for c in COLS:
        if c not in out:
            out[c] = ""
    out = out.astype(object).where(out.notna(), "")   # empty, not NaN, in every column
    for c in ("emendas_empenhado", "emendas_pago"):
        out[c] = _reais(out[c].astype("int64"))
    for c in ("meses", "n_votes", "n_party", "n_gov", "n_majority"):
        out[c] = out[c].map(lambda v: "" if v == "" else str(int(v)))
    out = out.assign(_k=pd.to_numeric(out.senador_id)).sort_values("_k").drop(columns="_k")[COLS]
    write_csv(out, data / "views" / f"senadores_{leg}.csv")
    linked = (out.campanha_sq_candidato != "").mean()
    _log(f"senadores_{leg}: {len(out)} senators, {linked:.0%} with their Senate race, "
         f"{(out.emendas.astype(int) > 0).mean():.0%} with amendments")
    return out
