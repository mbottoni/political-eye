"""The deputies' office allowance (CEAP, "cota parlamentar"): what each deputy spent, by month and kind.

    data/camara/cota/<year>.csv      deputado_id, mes, subcota, valor, documentos: net value (after the
                                     Câmara's disallowances) and receipts, per deputy, month and kind
    data/camara/cota/subcotas.csv    subcota code -> its description, as published
    data/camara/cota/sources.json    provenance of each year's file

From https://www.camara.leg.br/cotas/Ano-<year>.csv.zip, the Câmara's bulk file (refreshed daily). Rows of
party leadership offices (no deputy id) are dropped. Only sums are kept: no supplier, no passenger, no
document and no CPF (the file carries the deputy's and some suppliers' CPFs). See methodology/camara.md.
"""

from __future__ import annotations

import datetime as dt
import time
import zipfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from ..fetch import download_zip, log
from ..io import write_csv, write_sources

URL = "https://www.camara.leg.br/cotas/Ano-{year}.csv.zip"
FIRST = 2009
COLS = ["ideCadastro", "numSubCota", "txtDescricao", "vlrLiquido", "numMes", "numAno"]


def default_years() -> list[int]:
    """The previous and the current year: the Câmara keeps adding receipts for recent months."""
    y = dt.datetime.now(dt.UTC).year
    return [y - 1, y]


def fetch(years: list[int], raw: Path, pause: float = 4.0) -> dict[str, dict]:
    """Download each year's zip (the server answers 429 to quick successions, so requests are paced)."""
    out = {}
    for i, y in enumerate(years):
        if i:
            time.sleep(pause)
        src = download_zip(URL.format(year=y), raw / f"Ano-{y}.csv.zip")
        if src is not None:
            out[f"cota-{y}"] = asdict(src)
    return out


def read_year(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as f:
            t = pd.read_csv(f, sep=";", dtype=str, keep_default_na=False, usecols=COLS, encoding="utf-8-sig")
    t = t[t.ideCadastro.str.fullmatch(r"\d+")]
    return t.assign(valor=pd.to_numeric(t.vlrLiquido.str.replace(",", "."), errors="coerce").fillna(0.0))


def build_year(year: int, raw: Path, data: Path) -> dict:
    t = read_year(raw / f"Ano-{year}.csv.zip")
    t = t[t.numAno == str(year)]
    g = (t.groupby(["ideCadastro", "numMes", "numSubCota"]).agg(valor=("valor", "sum"), documentos=("valor", "size")).reset_index()
         .rename(columns={"ideCadastro": "deputado_id", "numMes": "mes", "numSubCota": "subcota"}))
    for c in ("deputado_id", "mes", "subcota"):
        g[c] = g[c].astype(int)
    g = g.sort_values(["deputado_id", "mes", "subcota"])
    write_csv(g.assign(valor=g.valor.round(2)), data / "cota" / f"{year}.csv")
    # Every description each code has carried, the latest kept (the Câmara reworded some over the years).
    names = t.drop_duplicates("numSubCota", keep="last")[["numSubCota", "txtDescricao"]].set_axis(["subcota", "descricao"], axis=1)
    ref = data / "cota" / "subcotas.csv"
    old = pd.read_csv(ref, dtype=str) if ref.exists() else pd.DataFrame(columns=["subcota", "descricao"])
    merged = pd.concat([old, names], ignore_index=True).drop_duplicates("subcota", keep="last")
    write_csv(merged.assign(_k=merged.subcota.astype(int)).sort_values("_k").drop(columns="_k"), ref)
    report = {"year": year, "rows": len(t), "deputies": int(g.deputado_id.nunique()), "valor": round(float(g.valor.sum()), 2)}
    log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report


def update(years: list[int], raw: Path, data: Path, *, skip_fetch: bool = False) -> list[dict]:
    if not skip_fetch:
        write_sources(data / "cota" / "sources.json", fetch(years, raw))
    return [build_year(y, raw, data) for y in years if (raw / f"Ano-{y}.csv.zip").exists()]
