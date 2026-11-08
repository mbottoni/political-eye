"""Summaries for the deputies' ranking page: ``data/site/ranking/``.

    deputados_<leg>.csv  one row per deputy of the legislature: the measures the ranking can weigh, as raw
                         values (the page turns them into percentiles and a weighted score, with the reader's
                         weights): roll-call participation, bills filed, rapporteur opinions, proposals
                         co-signed, co-voting ties across parties, and office-allowance spending per month in
                         office, with the state's median for comparison; plus the red-flag lists the deputy is
                         on, shown beside the score and never counted in it
    cota_<leg>.csv       office-allowance spending per deputy and kind over the legislature, for the breakdown

The office allowance (CEAP) differs by state (it covers flights to Brasília), so spending is compared with
deputies of the same state. See methodology/ranking.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..camara import graphs as g
from .common import csv, write_json

LEGS = (57, 56)
FLAG_LISTS = ("emendas_impedidas", "campanha_emendas", "concentracao")


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def allowance(data: Path, leg: int) -> pd.DataFrame:
    """Office-allowance spending per deputy and kind in the legislature's months."""
    parts = []
    for p in sorted((data / "camara" / "cota").glob("[0-9][0-9][0-9][0-9].csv")):
        t = pd.read_csv(p, dtype={"deputado_id": str})
        t["month"] = p.stem + "-" + t.mes.astype(int).map("{:02d}".format)
        parts.append(t[t.month.map(g.legislatura) == leg])
    if not parts:
        return pd.DataFrame(columns=["deputado_id", "subcota", "valor", "documentos"])
    return pd.concat(parts, ignore_index=True).groupby(["deputado_id", "subcota"], as_index=False)[["valor", "documentos"]].sum()


def build_leg(data: Path, leg: int) -> dict:
    out = data / "site" / "ranking"
    v = _read(data / "site" / "deputados" / f"deputados_{leg}.csv")
    if not len(v):
        return {}
    keep = ["pessoa", "deputado_id", "nome", "partido", "uf", "meses", "presenca", "votacoes_mandato", "projetos_autor", "propostas_autor",
            "relatorias", "propostas_coautor", "cross_share", "with_gov", "emendas_pago"]
    r = v[[c for c in keep if c in v.columns]].copy()
    for c in keep[5:]:
        if c in r:
            r[c] = pd.to_numeric(r[c], errors="coerce")

    # Office allowance over the legislature, per month in office, against the state's deputies.
    al = allowance(data, leg)
    names = _read(data / "camara" / "cota" / "subcotas.csv")
    csv(al.assign(valor=al.valor.round(2)).sort_values(["deputado_id", "subcota"]), out / f"cota_{leg}.csv")
    tot = al.groupby("deputado_id").valor.sum()
    r["cota_total"] = r.deputado_id.map(tot).fillna(0.0).round(2)
    r["cota_mes"] = (r.cota_total / r.meses).where(r.meses > 0).round(2)
    pub = al[al.subcota == 5].groupby("deputado_id").valor.sum()   # 5: publicity of their activity
    r["cota_divulgacao"] = (r.deputado_id.map(pub).fillna(0.0) / r.cota_total).where(r.cota_total > 0).round(4)
    full = r[r.meses >= 12]
    r["cota_mes_uf"] = r.uf.map(full.groupby("uf").cota_mes.median()).round(2)

    # The red-flag lists the deputy is on: shown, never scored.
    flags = []
    for k in FLAG_LISTS:
        t = _read(data / "site" / "alertas" / f"{k}.csv")
        if len(t) and "pessoa" in t:
            flags.append(t[["pessoa"]].drop_duplicates().assign(lista=k))
    fl = pd.concat(flags, ignore_index=True) if flags else pd.DataFrame(columns=["pessoa", "lista"])
    r["alertas"] = r.pessoa.map(fl.groupby("pessoa").lista.apply(lambda s: ";".join(sorted(set(s))))).fillna("")
    r = r.sort_values("deputado_id", key=lambda s: s.astype(int))
    csv(r, out / f"deputados_{leg}.csv")
    return {"deputies": len(r), "ranked": int((r.meses >= 12).sum()), "with_allowance": int((r.cota_total > 0).sum()),
            "allowance_median_month": float(full.cota_mes.median()) if len(full) else None, "subcotas": len(names),
            "participation_median": float(full.presenca.median()) if len(full) else None,
            "bills_median": float(full.projetos_autor.median()) if len(full) else None}


def build(data: Path) -> dict:
    out = {leg: build_leg(data, leg) for leg in LEGS}
    out = {k: v for k, v in out.items() if v}
    write_json({"legislaturas": sorted(out, reverse=True), "builds": out}, data / "site" / "ranking" / "resumo.json", digits=2)
    return out
