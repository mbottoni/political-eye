"""One row per municipality and year, across sources: ``data/views/municipios.csv``.

Joins on the IBGE code:

- the Portal da Transparência: amendments applied to the municipality, and
  the "Pix" ones (``especial``) among them;
- Siconfi: payroll against the Fiscal Responsibility Law's limits, and
  cash at the end of the year.

``methodology/views.md`` explains every column.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from ..io import write_csv

COLS = ["cod_ibge", "ente", "uf", "populacao", "ano", "emendas", "emendas_empenhado", "emendas_pago",
        "emendas_pix_pago", "emendas_pago_por_habitante", "dtp_pct", "situacao", "caixa_liquida_livre"]


def _log(msg: str) -> None:
    print(f"[views] {msg}", file=sys.stderr)


def _cents(s: pd.Series) -> pd.Series:
    return (pd.to_numeric(s, errors="coerce").fillna(0) * 100).round().astype("int64")


def _reais(c: pd.Series) -> pd.Series:
    return (c // 100).astype(str) + "." + (c % 100).astype(str).str.zfill(2)


def _years(folder: Path) -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted(folder.glob("*.csv"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build(data: Path) -> pd.DataFrame:
    ent = pd.read_csv(data / "siconfi" / "entes.csv", dtype=str, keep_default_na=False)
    em = pd.read_csv(data / "emendas" / "por_municipio.csv", dtype=str, keep_default_na=False)
    em = em.assign(e=_cents(em.empenhado), p=_cents(em.pago), n=pd.to_numeric(em.emendas).astype(int))
    em["pix"] = em.p.where(em.tipo == "especial", 0)
    by = em.groupby(["municipio_ibge", "ano"], as_index=False).agg(
        emendas=("n", "sum"), emendas_empenhado=("e", "sum"), emendas_pago=("p", "sum"), emendas_pix_pago=("pix", "sum"))
    by = by.rename(columns={"municipio_ibge": "cod_ibge"})

    pes = _years(data / "siconfi" / "pessoal")
    cai = _years(data / "siconfi" / "caixa")
    years = sorted(set(by.ano) | (set(pes.ano) if len(pes) else set()))
    grid = ent[["cod_ibge", "ente", "uf", "populacao"]].merge(pd.DataFrame({"ano": years}), how="cross")
    out = grid.merge(by, on=["cod_ibge", "ano"], how="left")
    if len(pes):
        out = out.merge(pes[["cod_ibge", "ano", "dtp_pct", "situacao"]], on=["cod_ibge", "ano"], how="left")
    if len(cai):
        out = out.merge(cai[["cod_ibge", "ano", "liquida_livre"]].rename(columns={"liquida_livre": "caixa_liquida_livre"}),
                        on=["cod_ibge", "ano"], how="left")
    for c in ("emendas", "emendas_empenhado", "emendas_pago", "emendas_pix_pago"):
        out[c] = out[c].fillna(0).astype("int64")
    pop = pd.to_numeric(out.populacao, errors="coerce")
    per = (out.emendas_pago / 100 / pop).where(pop > 0)
    out["emendas_pago_por_habitante"] = per.round(2).map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    for c in ("emendas_empenhado", "emendas_pago", "emendas_pix_pago"):
        out[c] = _reais(out[c])
    for c in COLS:
        if c not in out:
            out[c] = ""
    out = out.astype(object).where(out.notna(), "")
    out = out.assign(_c=pd.to_numeric(out.cod_ibge), _a=pd.to_numeric(out.ano)).sort_values(["_c", "_a"]).drop(columns=["_c", "_a"])
    write_csv(out[COLS], data / "views" / "municipios.csv")
    _log(f"municipios: {out.cod_ibge.nunique()} municipalities x {len(years)} years; "
         f"{(out.dtp_pct != '').sum()} with payroll data")
    return out[COLS]
