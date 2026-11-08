"""Summaries for the public contracts page: ``data/site/pncp/``.

    resumo.json        coverage, totals, distributions, concentration and the small aggregates the page draws
    diario.csv         per publication day and sphere: contracts published and their value (every contract)
    maiores.csv        the largest contracts (R$ 1 million or more), trimmed for the browser
    descartados.csv    contracts whose value is left out as a typo: over R$ 10 bn, or a town's contract
                       worth more than three years of the town's whole revenue
    fornecedores.csv   the largest suppliers, with what else links them to the State: sanctions, amendment
                       payments received directly, sales to election campaigns
    orgaos.csv         the largest buyers, and how concentrated their suppliers are (HHI)
    municipios.csv     per municipality, large contracts of its municipal bodies, per inhabitant
    partidos.csv       per party of the mayor in office when the contract was signed: municipal large
                       contracts per inhabitant, contracts with barred suppliers

Large contracts are the PNCP's of R$ 1 million or more (``data/pncp/contratos/``);
the daily totals count every contract. The history is read newest first, so
early days fill in over time; every figure says how many days it covers.
See methodology/pncp.md#the-explorer-page.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..ref.prefeitos import mayor_by_year
from .common import csv, write_json

START = "2021-09-01"      # the PNCP's first contracts under Lei 14.133
TOP = 3000
OBJ = 140
MIN_BUYER = 5             # contracts a buyer needs for its HHI to be shown
IMPLAUSIBLE = 15          # a global value above this many times the initial one is taken as a typo
CAP = 10e9                # no contract read is worth more: the largest real ones are 30-year PPPs near R$ 8 bn
TOWN_YEARS = 3            # nor a town's contract worth more than this many years of the town's whole revenue (RCL)
SANCTION_BARS = re.compile(r"^(Impedimento|Declaração de Inidoneidade|Suspensão$)")
# Parties that merged or were renamed, to their successor today, so terms compare across elections.
LINEAGE = {"PMDB": "MDB", "PR": "PL", "PRB": "REPUBLICANOS", "DEM": "UNIÃO", "PSL": "UNIÃO", "PPS": "CIDADANIA",
           "PTN": "PODE", "PHS": "PODE", "PSC": "PODE", "PEN": "PRD", "PATRIOTA": "PRD", "PRP": "PRD", "PTB": "PRD",
           "PSDC": "DC", "PT do B": "AVANTE", "SD": "SOLIDARIEDADE", "PROS": "SOLIDARIEDADE", "PPL": "PCdoB"}


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def _money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def lineage(p: pd.Series) -> pd.Series:
    return p.map(lambda x: LINEAGE.get(x, x))


def gini(v) -> float | None:
    v = np.sort(np.asarray([x for x in v if x > 0], dtype=float))
    n = len(v)
    if not n:
        return None
    return float(((2 * np.arange(1, n + 1) - n - 1) * v).sum() / (n * v.sum()))


def hhi(shares: pd.Series) -> float:
    return float((shares ** 2).sum())


def town_revenue(data: Path) -> pd.Series:
    """Each town's yearly net current revenue (RCL), from its latest payroll report read on Siconfi."""
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["cod_ibge", "ano", "periodo", "rcl", "rcl_ajustada"])
             for p in sorted((data / "siconfi" / "pessoal").glob("*.csv"))]
    if not parts:
        return pd.Series(dtype=float)
    t = pd.concat(parts, ignore_index=True)
    t["r"] = pd.to_numeric(t.rcl_ajustada, errors="coerce").fillna(pd.to_numeric(t.rcl, errors="coerce"))
    t = t[t.r > 0].sort_values(["cod_ibge", "ano", "periodo"])
    return t.groupby("cod_ibge").r.last()


def plausible(c: pd.DataFrame, rcl: pd.Series) -> pd.DataFrame:
    """The value each contract is counted at (``v``) and why it differs from the published one (``suspeito``).

    1: the global value is over IMPLAUSIBLE times the initial one (R$ 7.8 M initial, R$ 45.6 bn global):
       amendments and renewals multiply a contract, but not by that much, so it counts at its initial value.
    2: even so it is over CAP, or a town's contract over TOWN_YEARS years of the town's revenue (R$ 1 trillion
       of equipment for a town that takes in R$ 275 M a year): there is no value to trust, so it counts as zero.
    """
    v, vi = _money(c.valor_global), _money(c.valor_inicial)
    s = ((vi > 0) & (v > IMPLAUSIBLE * vi)).astype(int)
    v = v.where(s == 0, vi)
    town = pd.to_numeric(c.municipio_ibge.map(rcl), errors="coerce").where(c.esfera == "M")
    wild = (v > CAP) | (v > TOWN_YEARS * town)
    return c.assign(v=v.where(~wild, 0.0), suspeito=s.where(~wild, 2))


def contracts(src: Path, rcl: pd.Series) -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted((src / "contratos").glob("*.csv"))]
    if not parts:
        return pd.DataFrame(columns=["controle", "publicacao", "assinatura", "orgao_cnpj", "orgao", "esfera", "uf", "municipio_ibge",
                                     "categoria", "fornecedor_tipo", "fornecedor", "fornecedor_nome", "objeto", "valor_inicial",
                                     "valor_global", "v", "suspeito", "ano"])
    c = plausible(pd.concat(parts, ignore_index=True).drop_duplicates("controle", keep="last"), rcl)
    c["ano"] = c.assinatura.where(c.assinatura != "", c.publicacao).str[:4]
    return c


def build(data: Path) -> dict:
    src, out = data / "pncp", data / "site" / "pncp"
    days = _read(src / "dias.csv")
    daily = _read(src / "resumo_dia.csv")
    rcl = town_revenue(data)
    every = contracts(src, rcl)
    gone, c = every[every.suspeito == 2], every[every.suspeito != 2]   # values left out as typos: listed apart, counted nowhere
    sanc = _read(src / "contratos_sancionados.csv")
    if len(sanc):
        sanc = plausible(sanc, rcl)
        sanc = sanc[sanc.suspeito != 2]
    entes = _read(data / "siconfi" / "entes.csv")
    pop = pd.to_numeric(entes.set_index("cod_ibge").populacao, errors="coerce") if len(entes) else pd.Series(dtype=float)

    # ---------------------------------------------------------- coverage and every contract
    r: dict = {}
    first, last = (days.dia.min(), days.dia.max()) if len(days) else ("", "")
    span = (pd.Timestamp(last) - pd.Timestamp(START)).days + 1 if last else 0
    r["coverage"] = {"days_read": len(days), "first": first, "last": last, "since": START, "span_days": span,
                     "share": len(days) / span if span else 0.0,
                     "published": int(pd.to_numeric(days.get("publicados", pd.Series(dtype=str)), errors="coerce").sum()) if len(days) else 0}
    if len(daily):
        daily = daily.assign(contratos=pd.to_numeric(daily.contratos), valor=_money(daily.valor_global))
        # The daily totals sum published values: take out what the typos added (published minus counted).
        excess = every.assign(x=_money(every.valor_global) - every.v).query("x > 0").groupby(["publicacao", "esfera", "fornecedor_tipo"]).x.sum()
        key = pd.MultiIndex.from_frame(daily[["dia", "esfera", "fornecedor_tipo"]])
        daily["valor"] = (daily.valor - excess.reindex(key).fillna(0.0).values).clip(lower=0.0)
        d = daily.groupby(["dia", "esfera"], as_index=False)[["contratos", "valor"]].sum()
        csv(d.round(2).sort_values(["dia", "esfera"]), out / "diario.csv")
        r["totals"] = {
            "contratos": int(daily.contratos.sum()), "valor": float(daily.valor.sum()),
            "by_sphere": daily.groupby("esfera")[["contratos", "valor"]].sum().reset_index().to_dict("records"),
            "by_supplier": daily.groupby("fornecedor_tipo")[["contratos", "valor"]].sum().reset_index().to_dict("records"),
        }
    else:
        csv(pd.DataFrame(columns=["dia", "esfera", "contratos", "valor"]), out / "diario.csv")
        r["totals"] = {"contratos": 0, "valor": 0.0, "by_sphere": [], "by_supplier": []}

    # ---------------------------------------------------------- large contracts
    read = set(days.dia) if len(days) else set()
    on_days = c[c.publicacao.isin(read)]
    r["large"] = {
        "contratos": len(c), "valor": float(c.v.sum()),
        "on_days_read": {"contratos": len(on_days), "valor": float(on_days.v.sum())},
        "share_of_value": float(on_days.v.sum() / r["totals"]["valor"]) if r["totals"]["valor"] else None,
        "by_category": c.groupby("categoria").agg(contratos=("v", "size"), valor=("v", "sum")).reset_index()
        .sort_values(["valor", "categoria"], ascending=[False, True]).to_dict("records"),
        "by_sphere": c.groupby("esfera").agg(contratos=("v", "size"), valor=("v", "sum")).reset_index().to_dict("records"),
        "by_month": c.assign(mes=c.publicacao.str[:7]).groupby(["mes", "esfera"]).agg(contratos=("v", "size"), valor=("v", "sum"))
        .reset_index().to_dict("records"),
        "log_edges": [6 + i / 4 for i in range(0, 21)],
        "log_hist": np.histogram(np.log10(c.v[c.v >= 1e6]).clip(6, 11 - 1e-9), bins=[6 + i / 4 for i in range(0, 21)])[0].tolist(),
        "median": float(c.v.median()) if len(c) else None,
        "implausible": {"contratos": int((c.suspeito == 1).sum()), "publicado": float(_money(c.valor_global)[c.suspeito == 1].sum()),
                        "usado": float(c.v[c.suspeito == 1].sum()), "ratio": IMPLAUSIBLE},
        "left_out": {"contratos": len(gone), "publicado": float(_money(gone.valor_global).sum()), "cap": CAP, "town_years": TOWN_YEARS},
    }
    g = gone.assign(valor_inicial=_money(gone.valor_inicial), valor_publicado=_money(gone.valor_global), objeto=gone.objeto.str.slice(0, OBJ),
                    fornecedor_nome=gone.fornecedor_nome.where(gone.fornecedor_tipo != "PF", ""),   # the typo is the buyer's, not the person's
                    receita=pd.to_numeric(gone.municipio_ibge.map(rcl), errors="coerce").where(gone.esfera == "M"))
    csv(g.sort_values(["valor_publicado", "controle"], ascending=[False, True])[
        ["controle", "publicacao", "orgao", "esfera", "uf", "municipio_ibge", "fornecedor_nome", "objeto", "valor_inicial", "valor_publicado", "receita"]].round(2),
        out / "descartados.csv")
    top = c.sort_values(["v", "controle"], ascending=[False, True]).head(TOP).copy()
    top["objeto"] = top.objeto.str.slice(0, OBJ)
    csv(top[["controle", "publicacao", "assinatura", "orgao", "esfera", "uf", "municipio_ibge", "categoria", "fornecedor",
             "fornecedor_nome", "objeto", "v", "valor_global", "suspeito"]].rename(columns={"valor_global": "valor_publicado", "v": "valor"}).round(2),
        out / "maiores.csv")

    # ---------------------------------------------------------- suppliers
    sup = c.groupby("fornecedor").agg(nome=("fornecedor_nome", "last"), tipo=("fornecedor_tipo", "last"), contratos=("v", "size"),
                                      valor=("v", "sum"), orgaos=("orgao_cnpj", "nunique"), ufs=("uf", "nunique"),
                                      primeiro=("assinatura", "min"), ultimo=("assinatura", "max"))
    tot = sup.valor.sum()
    vals = sup.valor.sort_values(ascending=False)
    r["suppliers"] = {
        "n": int(len(sup)), "gini": gini(sup.valor),
        "top1_share": float(vals.head(max(1, len(vals) // 100)).sum() / tot) if tot else None,
        "top10_share": float(vals.head(max(1, len(vals) // 10)).sum() / tot) if tot else None,
        "lorenz": [[i / 50, float(vals[::-1].cumsum().iloc[min(len(vals) - 1, int(i / 50 * len(vals)))] / tot) if tot and i else 0.0]
                   for i in range(51)] if len(vals) else [],
        "by_type": c.groupby("fornecedor_tipo").agg(contratos=("v", "size"), valor=("v", "sum")).reset_index().to_dict("records"),
    }
    sup = sup.sort_values(["valor"], ascending=False).head(TOP)
    # What else ties them to the State.
    barred = set()
    for lista in ("ceis", "cnep"):
        t = _read(data / "sancoes" / f"{lista}.csv")
        if len(t):
            barred |= set(t[t.cpf_ou_cnpj_do_sancionado.str.fullmatch(r"\d{14}")].cpf_ou_cnpj_do_sancionado)
    sup["sancionada"] = sup.index.isin(barred).astype(int)
    sup["contratos_sancionada"] = sanc.groupby("fornecedor").controle.nunique().reindex(sup.index).fillna(0).astype(int) if len(sanc) else 0
    camp = []
    for y in ("2018", "2022", "2026"):
        f = _read(data / "tse" / y / "fornecedores.csv")
        if len(f):
            camp.append(f.assign(total=_money(f.total), n=pd.to_numeric(f.n_candidatos, errors="coerce").fillna(0)))
    camp = pd.concat(camp) if camp else pd.DataFrame(columns=["cnpj", "total", "n"])
    sup["campanhas"] = camp.groupby("cnpj").total.sum().reindex(sup.index).fillna(0.0)
    sup["campanhas_candidatos"] = camp.groupby("cnpj").n.sum().reindex(sup.index).fillna(0).astype(int)
    wanted = set(sup.index)
    em = []
    for p in sorted((data / "emendas" / "pagamentos").glob("*.csv")):
        t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["favorecido", "valor"])
        t = t[t.favorecido.isin(wanted)]
        if len(t):
            em.append(t.assign(valor=_money(t.valor)))
    em = pd.concat(em).groupby("favorecido").valor.sum() if em else pd.Series(dtype=float)
    sup["emendas"] = em.reindex(sup.index).fillna(0.0)
    sup = sup.reset_index().rename(columns={"fornecedor": "cnpj"})
    csv(sup.round(2), out / "fornecedores.csv")
    r["suppliers"]["linked"] = {"sancionadas": int(sup.sancionada.sum()), "campanhas": int((sup.campanhas > 0).sum()),
                                "emendas": int((sup.emendas > 0).sum()), "of": int(len(sup))}

    # ---------------------------------------------------------- buyers
    by = c.groupby(["orgao_cnpj", "fornecedor"]).v.sum().reset_index()
    share = by.v / by.groupby("orgao_cnpj").v.transform("sum")
    h = by.assign(s=share).groupby("orgao_cnpj").s.apply(hhi)
    top_sup = by.sort_values(["orgao_cnpj", "v"], ascending=[True, False]).drop_duplicates("orgao_cnpj").set_index("orgao_cnpj")
    org = c.groupby("orgao_cnpj").agg(orgao=("orgao", "last"), esfera=("esfera", "last"), uf=("uf", "last"),
                                      municipio_ibge=("municipio_ibge", "last"), contratos=("v", "size"), valor=("v", "sum"),
                                      fornecedores=("fornecedor", "nunique"))
    org["hhi"] = h.reindex(org.index).where(org.contratos >= MIN_BUYER)
    org["maior_fornecedor"] = top_sup.fornecedor.reindex(org.index)
    org["maior_fornecedor_nome"] = c.drop_duplicates("fornecedor").set_index("fornecedor").fornecedor_nome.reindex(org.maior_fornecedor).values
    org["maior_share"] = (top_sup.v.reindex(org.index) / org.valor).round(4)
    hh = org.hhi.dropna()
    r["buyers"] = {"n": int(len(org)), "with_hhi": int(len(hh)), "hhi_median": float(hh.median()) if len(hh) else None,
                   "hhi_hist": np.histogram(hh, bins=[i / 20 for i in range(21)])[0].tolist() if len(hh) else [],
                   "single_supplier": int((org[org.contratos >= MIN_BUYER].fornecedores == 1).sum())}
    org = org.sort_values("valor", ascending=False).head(TOP).reset_index()
    csv(org.round(4), out / "orgaos.csv")

    # ---------------------------------------------------------- places
    by_uf = c.groupby("uf").agg(contratos=("v", "size"), valor=("v", "sum")).reset_index()
    uf_pop = entes.assign(p=pd.to_numeric(entes.populacao, errors="coerce"), ibge=entes.cod_ibge.str[:2]).groupby(["uf", "ibge"]).p.sum().reset_index() if len(entes) else pd.DataFrame(columns=["uf", "ibge", "p"])
    by_uf = by_uf.merge(uf_pop, on="uf", how="left").rename(columns={"p": "populacao"})
    by_uf["por_habitante"] = (by_uf.valor / by_uf.populacao).round(2)
    r["by_uf"] = by_uf.sort_values("uf").to_dict("records")
    m = c[c.esfera == "M"]
    mun = m.groupby("municipio_ibge").agg(contratos=("v", "size"), valor=("v", "sum"), fornecedores=("fornecedor", "nunique")).reset_index()
    names = entes.set_index("cod_ibge") if len(entes) else pd.DataFrame(columns=["ente", "uf"])
    mun["municipio"] = mun.municipio_ibge.map(names.ente).fillna("")
    mun["uf"] = mun.municipio_ibge.map(names.uf).fillna("")
    mun["populacao"] = mun.municipio_ibge.map(pop)
    mun["por_habitante"] = (mun.valor / mun.populacao).round(2)
    csv(mun.rename(columns={"municipio_ibge": "cod_ibge"}).round(2).sort_values("cod_ibge"), out / "municipios.csv")

    # ---------------------------------------------------------- mayors' parties
    pre = _read(data / "ref" / "prefeitos.csv")
    years = sorted({int(y) for y in m.ano if y.isdigit() and int(y) >= 2017})
    if len(pre) and years:
        mb = mayor_by_year(pre, years)
        mb["partido"] = lineage(mb.partido)
        mb["pop"] = mb.cod_ibge.map(pop).fillna(0.0)
        gov = mb.groupby("partido").agg(municipios=("cod_ibge", "nunique"), pop_anos=("pop", "sum")).reset_index()
        mm = m[m.ano.str.isdigit()].assign(exercicio=lambda t: t.ano.astype(int)).merge(
            mb[["exercicio", "cod_ibge", "partido"]], left_on=["exercicio", "municipio_ibge"], right_on=["exercicio", "cod_ibge"], how="left")
        mm["partido"] = mm.partido.fillna("")
        pc = mm[mm.partido != ""].groupby("partido").agg(contratos=("v", "size"), valor=("v", "sum"),
                                                         municipios_com_contratos=("municipio_ibge", "nunique")).reset_index()
        ms = sanc[(sanc.esfera == "M") & sanc.cobre.isin(["sim", "possivel"])].copy() if len(sanc) else pd.DataFrame(columns=["assinatura", "municipio_ibge", "controle"])
        if len(ms):
            ms["exercicio"] = pd.to_numeric(ms.assinatura.str[:4], errors="coerce")
            ms = ms.merge(mb[["exercicio", "cod_ibge", "partido"]], left_on=["exercicio", "municipio_ibge"], right_on=["exercicio", "cod_ibge"])
        sc = ms.groupby("partido").controle.nunique() if len(ms) else pd.Series(dtype=int)
        pt = gov.merge(pc, on="partido", how="left").fillna({"contratos": 0, "valor": 0.0, "municipios_com_contratos": 0})
        pt["sancionadas"] = pt.partido.map(sc).fillna(0).astype(int)
        pt["por_habitante_ano"] = (pt.valor / pt.pop_anos).where(pt.pop_anos > 0).round(4)
        pt["contratos_por_milhao_hab"] = (pt.contratos / pt.pop_anos * 1e6).where(pt.pop_anos > 0).round(3)
        for col in ("contratos", "municipios_com_contratos"):
            pt[col] = pt[col].astype(int)
        csv(pt.round(2).sort_values("partido"), out / "partidos.csv")
        r["parties"] = {"years": years, "attributed": float(mm[mm.partido != ""].v.sum() / mm.v.sum()) if len(mm) and mm.v.sum() else None}
    else:
        csv(pd.DataFrame(columns=["partido", "municipios", "pop_anos", "contratos", "valor", "municipios_com_contratos", "sancionadas",
                                  "por_habitante_ano", "contratos_por_milhao_hab"]), out / "partidos.csv")
        r["parties"] = {"years": [], "attributed": None}

    # ---------------------------------------------------------- barred suppliers
    if len(sanc):
        sv = sanc
        r["sanctioned"] = {"by_cobre_sphere": sv.groupby(["cobre", "esfera"]).agg(contratos=("controle", "nunique"), valor=("v", "sum"))
                           .reset_index().to_dict("records"),
                           "suppliers": int(sv.fornecedor.nunique())}
    else:
        r["sanctioned"] = {"by_cobre_sphere": [], "suppliers": 0}

    write_json(r, out / "resumo.json", digits=4)
    return {"days": len(days), "large": len(c), "suppliers": int(r["suppliers"]["n"]), "buyers": int(r["buyers"]["n"])}
