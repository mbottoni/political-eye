"""Summaries for the municipal finances page: ``data/site/siconfi/``.

    resumo.json        coverage, status counts and distributions by year, by state and town size, the yearly
                       change in payroll (election years marked)
    anos/YYYY.csv      per municipality read that year: payroll and its share of revenue, the legal status,
                       unrestricted net cash, amendments paid, and the mayor's party
    uf/<UF>.json       per municipality of a state, every year (for the town profile) and its mayors
    partidos.csv       per year and party of the mayor in office: towns read, how many break each payroll
                       limit, the median payroll share, how many end the year with negative free cash

Payroll and its limits come from the Fiscal Management Report (RGF Annex 01),
cash from the year's last report (Annex 05). The history is being read, so
every figure says how many towns it covers. See methodology/siconfi.md#the-explorer-page.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..ref.prefeitos import mayor_by_year
from .common import csv, write_json
from .pncp import lineage

STATUS = ["abaixo", "acima_alerta", "acima_prudencial", "acima_maximo"]
SIZES = [(0, 5_000, "under 5k"), (5_000, 20_000, "5k–20k"), (20_000, 100_000, "20k–100k"), (100_000, 500_000, "100k–500k"),
         (500_000, float("inf"), "500k+")]
ELECTION_YEARS = (2016, 2020, 2024)
MIN_PARTY = 30   # towns a party must govern among those read for its shares to be shown


def _read_years(folder: Path) -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted(folder.glob("*.csv"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def size_class(pop: pd.Series) -> pd.Series:
    out = pd.Series("", index=pop.index)
    for lo, hi, name in SIZES:
        out = out.mask((pop >= lo) & (pop < hi), name)
    return out


def _q(v: pd.Series) -> dict:
    v = v.dropna()
    if v.empty:
        return {"n": 0}
    q = v.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    return {"n": int(len(v)), "p10": q[0.1], "p25": q[0.25], "p50": q[0.5], "p75": q[0.75], "p90": q[0.9]}


def town_payments(data: Path, entes: pd.DataFrame) -> pd.DataFrame:
    """Amendment payments to each municipality's own CNPJ, by payment year: ``total`` and ``pix`` (special transfers).

    ``data/emendas/por_municipio.csv`` counts only amendments applied to one municipality; "Pix" transfers are
    mostly recorded as ``MÚLTIPLO`` there, so they are found here by who was paid instead.
    """
    cnpj = dict(zip(entes.cnpj, entes.cod_ibge))
    codes = [pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo", "tipo"]) for p in sorted((data / "emendas" / "emendas").glob("*.csv"))]
    especial = set(pd.concat(codes).query("tipo == 'especial'").codigo) if codes else set()
    parts = []
    for p in sorted((data / "emendas" / "pagamentos").glob("*.csv")):
        t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo_emenda", "ano_mes", "favorecido", "valor"])
        t = t[t.favorecido.isin(cnpj)]
        if len(t):
            v = _num(t.valor).fillna(0.0)
            parts.append(pd.DataFrame({"cod_ibge": t.favorecido.map(cnpj), "ano": t.ano_mes.str[:4].astype(int), "total": v,
                                       "pix": v.where(t.codigo_emenda.isin(especial), 0.0)}))
    if not parts:
        return pd.DataFrame(columns=["cod_ibge", "ano", "total", "pix"])
    return pd.concat(parts).groupby(["cod_ibge", "ano"], as_index=False)[["total", "pix"]].sum()


def build(data: Path) -> dict:
    src, out = data / "siconfi", data / "site" / "siconfi"
    entes = pd.read_csv(src / "entes.csv", dtype=str, keep_default_na=False)
    entes["habitantes"] = _num(entes.populacao)
    pes, cai = _read_years(src / "pessoal"), _read_years(src / "caixa")
    con = pd.read_csv(src / "consultas.csv", dtype=str, keep_default_na=False) if (src / "consultas.csv").exists() else pd.DataFrame(columns=["cod_ibge", "ano", "linhas"])

    if len(pes):
        pes = pes.assign(ano=pes.ano.astype(int), dtp_pct=_num(pes.dtp_pct), rcl=_num(pes.rcl_ajustada).fillna(_num(pes.rcl)), dtp=_num(pes.dtp))
        pes["situacao"] = pes.situacao.where(pes.situacao != "", np.where(pes.dtp_pct.notna(), "abaixo", ""))
        pes = pes.sort_values(["cod_ibge", "ano", "periodicidade", "periodo"]).drop_duplicates(["cod_ibge", "ano"], keep="last")
    else:
        pes = pd.DataFrame(columns=["cod_ibge", "ano", "dtp_pct", "rcl", "dtp", "situacao"])
    if len(cai):
        cai = cai.assign(ano=cai.ano.astype(int), liquida_livre=_num(cai.liquida_livre), liquida_total=_num(cai.liquida_total))
        cai = cai.drop_duplicates(["cod_ibge", "ano"], keep="last")
    else:
        cai = pd.DataFrame(columns=["cod_ibge", "ano", "liquida_livre", "liquida_total"])

    # Amendments paid straight to each town's own CNPJ (the prefeitura), every type and the "Pix" transfers.
    pay = town_payments(data, entes)
    emt = pay.set_index(["cod_ibge", "ano"]).total
    emp = pay.set_index(["cod_ibge", "ano"]).pix

    t = pes[["cod_ibge", "ano", "dtp_pct", "situacao", "rcl", "dtp"]].merge(cai[["cod_ibge", "ano", "liquida_livre", "liquida_total"]], on=["cod_ibge", "ano"], how="outer")
    t = t.merge(entes[["cod_ibge", "ente", "uf", "regiao", "habitantes"]], on="cod_ibge", how="left")
    key = pd.MultiIndex.from_arrays([t.cod_ibge, t.ano])
    t["emendas"] = emt.reindex(key).fillna(0.0).values
    t["pix"] = emp.reindex(key).fillna(0.0).values
    t["caixa_hab"] = (t.liquida_livre / t.habitantes).round(2)
    t["emendas_hab"] = (t.emendas / t.habitantes).round(2)
    t["pix_hab"] = (t.pix / t.habitantes).round(2)
    t["porte"] = size_class(t.habitantes.fillna(0))

    pre = pd.read_csv(data / "ref" / "prefeitos.csv", dtype=str, keep_default_na=False) if (data / "ref" / "prefeitos.csv").exists() else pd.DataFrame()
    years = sorted(int(y) for y in t.ano.dropna().unique())
    if len(pre) and years:
        mb = mayor_by_year(pre, years)
        mb["partido_atual"] = lineage(mb.partido)
        t = t.merge(mb[["exercicio", "cod_ibge", "partido", "partido_atual", "nome_urna"]].rename(columns={"exercicio": "ano", "nome_urna": "prefeito"}),
                    on=["cod_ibge", "ano"], how="left")
    else:
        t[["partido", "partido_atual", "prefeito"]] = ""
    t[["partido", "partido_atual", "prefeito"]] = t[["partido", "partido_atual", "prefeito"]].fillna("")

    # ---------------------------------------------------------- per year tables
    yd = out / "anos"
    yd.mkdir(parents=True, exist_ok=True)
    keep = set()
    cols = ["cod_ibge", "ente", "uf", "habitantes", "dtp_pct", "situacao", "rcl", "dtp", "liquida_livre", "caixa_hab", "emendas", "pix", "pix_hab",
            "partido", "partido_atual", "prefeito"]
    for y, g in t.groupby("ano"):
        p = yd / f"{int(y)}.csv"
        csv(g[cols].round({"dtp_pct": 2, "rcl": 2, "dtp": 2, "liquida_livre": 2, "emendas": 2, "pix": 2}).sort_values("cod_ibge"), p)
        keep.add(p.name)
    for p in yd.glob("*.csv"):
        if p.name not in keep:
            p.unlink()

    # ---------------------------------------------------------- per state shards for the town profile
    ud = out / "uf"
    ud.mkdir(parents=True, exist_ok=True)
    mayors = pre.sort_values(["cod_ibge", "data_eleicao"]) if len(pre) else pd.DataFrame(columns=["cod_ibge"])
    ukeep = set()
    for uf, g in entes.groupby("uf"):
        towns = {}
        rows = t[t.uf == uf].sort_values(["cod_ibge", "ano"])
        by_town = dict(tuple(rows.groupby("cod_ibge")))
        pays = pay[pay.cod_ibge.str[:2] == g.cod_ibge.iloc[0][:2]]
        by_pay = {c: x[["ano", "total", "pix"]].round(2).values.tolist() for c, x in pays.sort_values(["cod_ibge", "ano"]).groupby("cod_ibge")}
        for _, e in g.iterrows():
            c = e.cod_ibge
            r = by_town.get(c)
            years_rows = r[["ano", "dtp_pct", "situacao", "rcl", "dtp", "liquida_livre"]].values.tolist() if r is not None else []
            am = [[int(a), v, x] for a, v, x in by_pay.get(c, [])]
            mm = mayors[mayors.cod_ibge == c][["ano", "partido", "nome_urna", "suplementar", "data_eleicao"]].values.tolist() if len(mayors) else []
            towns[c] = {"n": e.ente, "p": None if pd.isna(e.habitantes) else int(e.habitantes), "y": years_rows, "a": am, "m": mm}
        p = ud / f"{uf}.json"
        write_json(towns, p, digits=2)
        ukeep.add(p.name)
    for p in ud.glob("*.json"):
        if p.name not in ukeep:
            p.unlink()

    # ---------------------------------------------------------- summaries
    r: dict = {"towns": int(len(entes)), "years": years}
    q = con.assign(ano=_num(con.ano), linhas=_num(con.linhas))
    r["coverage"] = [{"ano": int(y), "consultados": int(g.cod_ibge.nunique()), "com_relatorio": int(g[g.linhas > 0].cod_ibge.nunique()),
                      "pessoal": int(t[(t.ano == y) & t.dtp_pct.notna()].cod_ibge.nunique()),
                      "caixa": int(t[(t.ano == y) & t.liquida_livre.notna()].cod_ibge.nunique())} for y, g in q.groupby("ano")]
    pp = t[t.dtp_pct.notna()]
    r["status_by_year"] = [{"ano": int(y), **{s: int((g.situacao == s).sum()) for s in STATUS}, **_q(g.dtp_pct)} for y, g in pp.groupby("ano")]
    edges = [20 + 2 * i for i in range(0, 31)]
    r["hist"] = {"edges": edges, "years": {str(int(y)): np.histogram(g.dtp_pct.clip(edges[0], edges[-1] - 1e-9), bins=edges)[0].tolist() for y, g in pp.groupby("ano")}}

    def shares(g):
        n = len(g)
        return {"n": n, "alerta": int(g.situacao.isin(STATUS[1:]).sum()), "prudencial": int(g.situacao.isin(STATUS[2:]).sum()),
                "maximo": int((g.situacao == "acima_maximo").sum()), "mediana": float(g.dtp_pct.median()) if n else None}
    r["by_uf"] = [{"ano": int(y), "uf": uf, **shares(g)} for (y, uf), g in pp.groupby(["ano", "uf"])]
    r["by_size"] = [{"ano": int(y), "porte": s, **shares(g)} for (y, s), g in pp.groupby(["ano", "porte"]) if s]
    cc = t[t.liquida_livre.notna()]
    r["cash_by_year"] = [{"ano": int(y), "n": int(len(g)), "negativa": int((g.liquida_livre < 0).sum()), **_q(g.caixa_hab)} for y, g in cc.groupby("ano")]
    # Payroll growth from one year to the next, in the same town (nominal R$).
    d = pp.sort_values(["cod_ibge", "ano"])
    d = d.assign(prev=d.groupby("cod_ibge").dtp.shift(), prev_ano=d.groupby("cod_ibge").ano.shift())
    d = d[(d.ano - d.prev_ano == 1) & (d.prev > 0)]
    d["growth"] = d.dtp / d.prev - 1
    r["growth"] = [{"ano": int(y), "eleicao": int(y) in ELECTION_YEARS, **_q(g.growth)} for y, g in d.groupby("ano")]

    # Mayors' parties.
    pa = pp[pp.partido_atual != ""]
    rows = []
    for (y, party), g in pa.groupby(["ano", "partido_atual"]):
        c = cc[(cc.ano == y) & (cc.partido_atual == party)]
        rows.append({"ano": int(y), "partido": party, **shares(g), "caixa_n": int(len(c)), "caixa_negativa": int((c.liquida_livre < 0).sum()),
                     "caixa_hab_mediana": float(c.caixa_hab.median()) if len(c) else None,
                     "pix_hab_mediana": float(g.pix_hab.median()) if len(g) else None})
    pt = pd.DataFrame(rows, columns=["ano", "partido", "n", "alerta", "prudencial", "maximo", "mediana", "caixa_n", "caixa_negativa",
                                     "caixa_hab_mediana", "pix_hab_mediana"])
    csv(pt.round(4).sort_values(["ano", "partido"]), out / "partidos.csv")
    r["min_party"] = MIN_PARTY
    r["status"] = STATUS
    r["sizes"] = [s[2] for s in SIZES]
    write_json(r, out / "resumo.json", digits=4)
    return {"years": years, "town_years": int(len(pp)), "cash_years": int(len(cc))}
