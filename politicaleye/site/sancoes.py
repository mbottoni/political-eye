"""Summaries for the sanctions page: ``data/site/sancoes/``.

    resumo.json          the tiles and every small aggregate the page draws
    empresas.csv         one row per sanctioned company or organisation (CNPJ): its lists, its sanctions,
                         and the public money it received
    empresas/<nn>.json   per CNPJ, sharded by its first two digits: sanctions, contracts, amendment
                         payments, campaign sales, CEPIM agreements and leniency agreements
    multas.csv           CNEP fines on companies
    leniencia.csv        one row per leniency agreement, with the amounts quoted in its terms
    expirando.csv        company sanctions that end within 90 days of the snapshot
    mudancas.csv         entries and exits per day, list and kind of person
    recentes.csv         the latest 500 changes about companies

People are counted, never named: every table that names someone holds only
companies and organisations (14-digit CNPJs or foreign codes). Every rule is
in methodology/sancoes.md#the-explorer-page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .common import csv, write_json

# Sanctions that bar contracting: the same rule as politicaleye.pncp.build.BARS.
BARS = re.compile(r"^(Impedimento|Declaração de Inidoneidade|Suspensão$)")
ELECTIONS = {"2018": "2018-10-07", "2022": "2022-10-02", "2026": "2026-10-04"}
SOON = 90            # days: "expiring soon"
RECENT = 500         # latest company changes kept for the page
SPHERES = ["FEDERAL", "ESTADUAL", "MUNICIPAL"]
LAWS = {
    "LEI 8429": "Improbidade law (8.429/1992)", "LEI 14133": "Procurement law (14.133/2021)",
    "LEI 8666": "Former procurement law (8.666/1993)", "LEI 12846": "Anti-corruption law (12.846/2013)",
    "LEI 10520": "Pregão law (10.520/2002)", "LEI 13303": "State companies law (13.303/2016)",
    "LEI 9433 (BA)": "Bahia procurement law (9.433/2005)", "LEI 8443": "TCU organic law (8.443/1992)",
    "LEI 45902 (MG)": "Minas Gerais state law 45.902", "LEI 13105": "Civil procedure code (13.105/2015)",
    "LEI 12462": "RDC law (12.462/2011)", "LEI 12529": "Competition law (12.529/2011)",
    "CÓDIGO DE PROCESSO PENAL": "Criminal procedure code",
}
COMPANY = r"\d{14}|EX.*"


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def _money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _snapshot(src: Path) -> tuple[str, str]:
    s = json.loads((src / "sources.json").read_text()) if (src / "sources.json").exists() else {}
    return s.get("ceis", {}).get("date", ""), s.get("cepim", {}).get("date", "")


def law(text: str) -> str:
    """``"LEI 8666 - ART. 87, IV - PELA ..."`` -> ``"LEI 8666"``."""
    return text.split(" - ")[0].strip() if text else ""


def article(text: str) -> str:
    """``"LEI 8666 - ART. 87, IV - PELA ..."`` -> ``"LEI 8666 - ART. 87, IV"``."""
    return " - ".join(p.strip() for p in text.split(" - ")[:2]).strip(" -") if text else ""


_NUM = r"(\d{1,3}(?:\.\d{3})*,\d{2})"


def amounts(terms: str) -> tuple[float | None, str, float | None]:
    """The total and fine a leniency agreement's terms quote: ``(total, currency, fine)``."""
    def num(s: str) -> float:
        return float(s.replace(".", "").replace(",", "."))
    total, cur, fine = None, "", None
    m = re.search(r"valor (?:total|global) de (R\$|US\$|USD)?\s*" + _NUM + r"\s*(EUROS?|D[ÓO]LARES)?", terms, re.I)
    if m:
        total = num(m[2])
        cur = "EUR" if m[3] and m[3].upper().startswith("EURO") else "USD" if (m[1] or "").startswith("US") or m[3] else "BRL"
    m = re.search(r"dos quais (?:R\$)?\s*" + _NUM + r"\s*(?:EUROS?\s*)?correspond\w* a multa", terms, re.I)
    if m:
        fine = num(m[1])
    return total, cur, fine


def in_force(start: pd.Series, end: pd.Series, when, *, month: bool = False) -> pd.Series:
    """Whether a sanction ran at ``when`` (an ISO day, scalar or Series); with ``month``, ``when`` is ``YYYY-MM``
    and any overlap with that month counts."""
    if month:
        start, end = start.str[:7], end.str[:7]
    return (start != "") & (start <= when) & ((end == "") | (when <= end))


def federal_scope(s: pd.DataFrame) -> pd.Series:
    """Whether a sanction reaches federal bodies, which pay amendments straight to a company: sim, possivel, nao."""
    everywhere = s.abrangencia.str.startswith("Todas as Esferas")
    sphere = s.abrangencia.str.startswith(("Em todos os Poderes da Esfera", "Na Esfera"))
    federal = s.esfera == "FEDERAL"
    out = pd.Series("possivel", index=s.index)
    out = out.mask(~federal & (s.esfera != ""), "nao")
    out = out.mask(federal & sphere, "sim")
    return out.mask(everywhere, "sim")


RANK = {"sim": 3, "possivel": 2, "nao": 1, "": 0}


def _best(s: pd.Series) -> str:
    return max(s, key=lambda v: RANK.get(v, 0)) if len(s) else ""


def _hist(values: pd.Series, edges: list[float]) -> list[int]:
    v = values.dropna().clip(edges[0], edges[-1] - 1e-9)
    return np.histogram(v, bins=edges)[0].tolist()


def _quant(values: pd.Series) -> dict:
    v = values.dropna()
    if v.empty:
        return {"n": 0}
    q = v.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    return {"n": int(len(v)), "p10": q[0.1], "p25": q[0.25], "p50": q[0.5], "p75": q[0.75], "p90": q[0.9], "mean": v.mean()}


# ------------------------------------------------------------ the lists


def sanctions(src: Path) -> pd.DataFrame:
    """CEIS and CNEP as one frame with short column names."""
    rows = []
    for lista in ("ceis", "cnep"):
        t = _read(src / f"{lista}.csv")
        if t.empty:
            continue
        rows.append(pd.DataFrame({
            "lista": lista.upper(), "codigo": t.codigo_da_sancao, "tipo": t.tipo_de_pessoa,
            "doc": t.cpf_ou_cnpj_do_sancionado,
            "nome": t.razao_social_cadastro_receita.where(t.razao_social_cadastro_receita != "", t.nome_do_sancionado),
            "categoria": t.categoria_da_sancao, "inicio": t.data_inicio_sancao, "fim": t.data_final_sancao,
            "publicacao": t.data_publicacao, "origem_data": t.data_origem_informacao,
            "abrangencia": t.abragencia_da_sancao, "orgao": t.orgao_sancionador, "uf": t.uf_orgao_sancionador,
            "esfera": t.esfera_orgao_sancionador, "fundamentacao": t.fundamentacao_legal,
            "origem": t.origem_informacoes, "processo": t.numero_do_processo,
            "multa": _money(t.valor_da_multa) if "valor_da_multa" in t else 0.0}))
    cols = ["lista", "codigo", "tipo", "doc", "nome", "categoria", "inicio", "fim", "publicacao", "origem_data",
            "abrangencia", "orgao", "uf", "esfera", "fundamentacao", "origem", "processo", "multa"]
    s = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=cols)
    s["empresa"] = s.doc.str.fullmatch(COMPANY) & (s.tipo != "F")
    s["bars"] = s.categoria.str.match(BARS)
    return s


GROUP = re.compile(r"(?:[Gg]rupo econ[ôo]mico|antigo [Gg]rupo|[Gg]rupo)\s+([A-ZÀ-Ü][\wÀ-ü&\-]*(?:\s+[A-ZÀ-Ü][\wÀ-ü&\-]*){0,2})")


def leniency(src: Path) -> pd.DataFrame:
    le, ef = _read(src / "leniencia.csv"), _read(src / "leniencia_efeitos.csv")
    cols = ["id", "nome", "empresas", "cnpjs", "n_empresas", "inicio", "fim", "situacao", "orgao", "valor_total", "moeda",
            "multa", "efeitos", "termos"]
    if le.empty:
        return pd.DataFrame(columns=cols)
    eff = ef.groupby("id_do_acordo").efeito_do_acordo_de_leniencia.agg(lambda x: "; ".join(sorted(set(x)))) if not ef.empty else {}
    out = []
    for i, g in le.sort_values(["id_do_acordo", "cnpj_do_sancionado"]).groupby("id_do_acordo", sort=True):
        terms = g.termos_do_acordo.iloc[0]
        total, cur, fine = amounts(terms)
        grp = GROUP.search(terms)
        out.append({"id": i, "nome": f"{grp[1]} group" if grp else g.razao_social_cadastro_receita.iloc[0], "empresas": "; ".join(g.razao_social_cadastro_receita.drop_duplicates()),
                    "cnpjs": " ".join(g.cnpj_do_sancionado.drop_duplicates()), "n_empresas": g.cnpj_do_sancionado.nunique(),
                    "inicio": g.data_de_inicio_do_acordo.min(), "fim": g.data_de_fim_do_acordo.max(),
                    "situacao": g.situacao_do_acordo_de_lenienica.iloc[0], "orgao": g.orgao_sancionador.iloc[0],
                    "valor_total": total, "moeda": cur, "multa": fine, "efeitos": eff.get(i, "") if len(eff) else "",
                    "termos": re.sub(r"\s+", " ", terms)[:400]})
    return pd.DataFrame(out, columns=cols)


# ------------------------------------------------------------ public money


def amendment_payments(emendas: Path, cnpjs: set[str]) -> tuple[pd.DataFrame, pd.Series]:
    """Amendment payments to the given CNPJs (recipient, month, amendment code, value), and every amendment's
    total paid to anyone (by code), which is what each author's share is measured against."""
    parts, totals = [], []
    for p in sorted((emendas / "pagamentos").glob("*.csv")):
        t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo_emenda", "ano_mes", "favorecido", "valor"])
        t["valor"] = _money(t.valor)
        totals.append(t[t.codigo_emenda != ""].groupby("codigo_emenda").valor.sum())
        t = t[t.favorecido.isin(cnpjs)]
        if len(t):
            parts.append(t)
    total = pd.concat(totals).groupby(level=0).sum() if totals else pd.Series(dtype=float)
    if not parts:
        return pd.DataFrame(columns=["favorecido", "ano_mes", "codigo_emenda", "valor"]), total
    return pd.concat(parts).groupby(["favorecido", "ano_mes", "codigo_emenda"], as_index=False).valor.sum(), total


def amendments(emendas: Path) -> pd.DataFrame:
    """One row per amendment code: year, type and author."""
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo", "ano", "tipo", "autor_codigo", "autor"])
             for p in sorted((emendas / "emendas").glob("*.csv"))]
    if not parts:
        return pd.DataFrame(columns=["codigo", "ano", "tipo", "autor_codigo", "autor"])
    return pd.concat(parts).drop_duplicates("codigo").reset_index(drop=True)


def party_timeline(data: Path) -> pd.DataFrame:
    """Every month a deputy or senator appears in the chamber tables: pessoa, month, casa, partido, uf."""
    x = _read(data / "ref" / "politicians.csv")
    out = []
    for casa, folder, key in (("camara", "camara/deputies", "deputado_id"), ("senado", "senado/senators", "senador_id")):
        ids = x[x.fonte == casa].drop_duplicates("id").set_index("id").pessoa if len(x) else pd.Series(dtype=str)
        for p in sorted((data / folder).glob("*.csv")):
            t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=[key, "partido", "uf"])
            t = t.assign(pessoa=t[key].map(ids), month=p.stem, casa=casa).dropna(subset=["pessoa"])
            out.append(t[["pessoa", "month", "casa", "partido", "uf"]])
    if not out:
        return pd.DataFrame(columns=["pessoa", "month", "casa", "partido", "uf"])
    return pd.concat(out).drop_duplicates(["pessoa", "month"]).reset_index(drop=True)


def _mi(m: pd.Series) -> pd.Series:
    return m.str[:4].astype(int) * 12 + m.str[5:7].astype(int) - 1


def party_at(keys: pd.DataFrame, tl: pd.DataFrame) -> pd.DataFrame:
    """For rows of (pessoa, month), the party, state and chamber then: the latest month on or before it, else the first after."""
    cols = ["casa", "partido", "uf"]
    if keys.empty or tl.empty:
        return pd.DataFrame("", index=keys.index, columns=cols)
    k = keys.assign(_i=_mi(keys.month), _o=range(len(keys))).sort_values("_i")
    t = tl.assign(_i=_mi(tl.month)).sort_values("_i")[["pessoa", "_i", *cols]]
    back = pd.merge_asof(k, t, on="_i", by="pessoa", direction="backward")
    fwd = pd.merge_asof(k, t, on="_i", by="pessoa", direction="forward")
    out = back.set_index("_o")[cols].fillna(fwd.set_index("_o")[cols]).sort_index()
    out.index = keys.index
    return out.fillna("")


COLLECTIVE = {"bancada": "State bench", "comissao": "Committee", "relator": "Rapporteur-general"}


def while_barred(events: pd.DataFrame, s: pd.DataFrame, key: str, when: str, scope=None, *, month: bool = False) -> pd.Series:
    """For each event (a payment, a sale), the widest scope of a barring sanction in force then; "" when none."""
    bar = s[s.empresa & s.bars][["doc", "inicio", "fim", "esfera", "abrangencia"]]
    if events.empty or bar.empty:
        return pd.Series("", index=events.index)
    m = events[[key, when]].reset_index().merge(bar, left_on=key, right_on="doc")
    m = m[in_force(m.inicio, m.fim, m[when], month=month)]
    if m.empty:
        return pd.Series("", index=events.index)
    m["scope"] = scope(m) if scope else "sim"
    best = m.groupby("index").scope.agg(_best)
    return best.reindex(events.index, fill_value="")


def build(data: Path) -> dict:
    src, out = data / "sancoes", data / "site" / "sancoes"
    day, cepim_day = _snapshot(src)
    s = sanctions(src)
    if not day:
        day = s.origem_data.max() if len(s) else ""
    cep = _read(src / "cepim.csv")
    le = leniency(src)
    changes = _read(src / "changes.csv")
    s["vigente"] = in_force(s.inicio, s.fim, day)
    s["vencida"] = (s.fim != "") & (s.fim < day)

    comp = s[s.empresa]
    cnpjs = set(comp.doc) | set(cep.get("cnpj_entidade", [])) | {c for x in le.cnpjs for c in x.split()}

    # Amendment payments to sanctioned companies and CEPIM organisations; the scope that reached federal bodies.
    pay, paid_by_code = amendment_payments(data / "emendas", cnpjs)
    pay["barrado"] = while_barred(pay.rename(columns={"favorecido": "doc"}), s, "doc", "ano_mes", federal_scope, month=True)
    pay["ano"] = pay.ano_mes.str[:4]

    # Who sent that money: each amendment's author, and an individual author's party in the amendment's year.
    em = amendments(data / "emendas")
    x = _read(data / "ref" / "politicians.csv")
    who = x[x.fonte == "emendas"].drop_duplicates("id").set_index("id").pessoa if len(x) else pd.Series(dtype=str)
    em["pessoa"] = em.autor_codigo.map(who).where(em.tipo.isin(["individual", "especial"]))
    known = em[em.pessoa.notna()]
    em = em.join(party_at(pd.DataFrame({"pessoa": known.pessoa, "month": known.ano + "-07"}), party_timeline(data)))
    em[["pessoa", "casa", "partido", "uf"]] = em[["pessoa", "casa", "partido", "uf"]].fillna("")
    barred_pay = pay[pay.barrado != ""]
    em["pago"] = em.codigo.map(paid_by_code).fillna(0.0)
    em["pago_sancionadas"] = em.codigo.map(barred_pay.groupby("codigo_emenda").valor.sum()).fillna(0.0)
    em["pago_sim"] = em.codigo.map(pay[pay.barrado == "sim"].groupby("codigo_emenda").valor.sum()).fillna(0.0)
    paid = em[em.pago > 0]
    bp = barred_pay.merge(em[["codigo", "autor_codigo", "autor", "partido"]], left_on="codigo_emenda", right_on="codigo")

    au = paid.sort_values(["ano", "codigo"]).groupby("autor_codigo")[["autor", "tipo", "pessoa", "casa", "partido", "uf"]].last()
    au = au.join(paid.groupby("autor_codigo").agg(emendas=("codigo", "size"), pago_total=("pago", "sum"),
                                                  pago_sancionadas=("pago_sancionadas", "sum"), pago_sim=("pago_sim", "sum"),
                                                  primeiro=("ano", "min"), ultimo=("ano", "max")))
    au["empresas_sancionadas"] = bp.groupby("autor_codigo").favorecido.nunique().reindex(au.index).fillna(0).astype(int)
    au["kind"] = np.where(au.tipo.isin(list(COLLECTIVE)), au.tipo,
                          np.where(au.casa == "senado", "senador", np.where(au.casa == "camara", "deputado", "outro")))
    au["share"] = (au.pago_sancionadas / au.pago_total).where(au.pago_total > 0)
    au = au.reset_index()
    for c in ("pago_total", "pago_sancionadas", "pago_sim"):
        au[c] = au[c].round(2)
    au["share"] = au.share.round(6)

    ind = paid[paid.partido != ""]
    pt = ind.groupby("partido").agg(autores=("autor_codigo", "nunique"), emendas=("codigo", "size"), pago_total=("pago", "sum"),
                                    pago_sancionadas=("pago_sancionadas", "sum"), pago_sim=("pago_sim", "sum"))
    pt["autores_com_sancionadas"] = ind[ind.pago_sancionadas > 0].groupby("partido").autor_codigo.nunique().reindex(pt.index).fillna(0).astype(int)
    pt["empresas_sancionadas"] = bp[bp.partido != ""].groupby("partido").favorecido.nunique().reindex(pt.index).fillna(0).astype(int)
    pt["share"] = (pt.pago_sancionadas / pt.pago_total).where(pt.pago_total > 0).round(6)
    pt["share_sim"] = (pt.pago_sim / pt.pago_total).where(pt.pago_total > 0).round(6)
    pt = pt.reset_index()
    by_party_year = (ind.assign(ano=ind.ano).groupby(["partido", "ano"])[["pago", "pago_sancionadas"]].sum().reset_index())

    # Contracts: the PNCP's large contracts of these companies, and every contract signed while barred.
    big = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted((data / "pncp" / "contratos").glob("*.csv"))]
    big = pd.concat(big, ignore_index=True) if big else pd.DataFrame()
    sanc_c = _read(data / "pncp" / "contratos_sancionados.csv")
    ccols = ["controle", "assinatura", "orgao", "esfera", "uf", "fornecedor", "objeto", "valor_global"]
    contracts = pd.concat([x[ccols] for x in (big, sanc_c) if len(x)], ignore_index=True) if len(big) or len(sanc_c) else pd.DataFrame(columns=ccols)
    contracts = contracts[contracts.fornecedor.isin(cnpjs)].drop_duplicates("controle")
    cobre = sanc_c.groupby("controle").cobre.agg(_best) if len(sanc_c) else pd.Series(dtype=str)
    contracts["cobre"] = contracts.controle.map(cobre).fillna("")
    contracts["valor_global"] = _money(contracts.valor_global)

    # Campaign suppliers on election day.
    tse = []
    for year, eday in ELECTIONS.items():
        f = _read(data / "tse" / year / "fornecedores.csv")
        if f.empty:
            continue
        f = f.assign(ano=year, dia=eday, total=_money(f.total))
        f["barrado"] = while_barred(f.rename(columns={"cnpj": "doc"}), s, "doc", "dia")
        tse.append(f)
    tse = pd.concat(tse, ignore_index=True) if tse else pd.DataFrame(columns=["cnpj", "nome", "total", "n_candidatos", "ano", "barrado"])
    tse_s = tse[tse.cnpj.isin(cnpjs)]

    resumo = {"snapshot": day, "cepim_snapshot": cepim_day}
    resumo["tiles"] = {
        "ceis": int((s.lista == "CEIS").sum()), "cnep": int((s.lista == "CNEP").sum()), "cepim": len(cep),
        "cepim_entidades": int(cep.cnpj_entidade.nunique()) if len(cep) else 0,
        "acordos": len(le), "acordos_empresas": int(le.n_empresas.sum()) if len(le) else 0,
        "empresas": int(comp.doc.nunique()), "pessoas": int((s.tipo == "F").sum()),
        "pessoas_distintas": int(s[s.tipo == "F"].doc.nunique()),
        "vigentes": int(s.vigente.sum()), "vencidas": int(s.vencida.sum()),
        "barram": int(s.bars.sum()), "sem_prazo": int((s.fim == "").sum()),
        "multas_n": int((s.multa > 0).sum()), "multas_total": float(s.multa.sum()),
    }

    def kind(t):
        return np.where(t.empresa, "empresa", np.where(t.tipo == "F", "pessoa", "outro"))
    s["kind"] = kind(s)
    resumo["lists"] = s.groupby(["lista", "kind"]).size().unstack(fill_value=0).reset_index().to_dict("records")
    resumo["categories"] = (s.groupby(["lista", "categoria", "kind"]).size().unstack(fill_value=0).reset_index()
                            .assign(barra=lambda t: t.categoria.str.match(BARS)).to_dict("records"))
    resumo["spheres"] = s.groupby(["lista", "esfera"]).size().rename("n").reset_index().to_dict("records")
    resumo["sphere_kind"] = s.groupby(["esfera", "kind"]).size().unstack(fill_value=0).reset_index().to_dict("records")
    sy = s.assign(ano=s.inicio.str[:4], esf=s.esfera.where(s.esfera.isin(SPHERES), "outra"))
    resumo["start_year"] = sy.groupby(["ano", "esf"]).size().unstack(fill_value=0).reset_index().to_dict("records")

    # By the sanctioning body's state, state and municipal bodies only; per million inhabitants.
    entes = _read(data / "siconfi" / "entes.csv")
    pop = entes.assign(p=pd.to_numeric(entes.populacao, errors="coerce"), ibge=entes.cod_ibge.str[:2]).groupby(["uf", "ibge"]).p.sum() if len(entes) else pd.Series(dtype=float)
    local = s[s.esfera.isin(["ESTADUAL", "MUNICIPAL"]) & (s.uf != "")]
    uf = local.groupby(["uf", "esfera"]).size().unstack(fill_value=0).reindex(columns=["ESTADUAL", "MUNICIPAL"], fill_value=0)
    uf["total"] = uf.sum(axis=1)
    uf = uf.reset_index()
    pop = pop.reset_index()
    uf = uf.merge(pop, on="uf", how="left")
    uf["por_milhao"] = (uf.total / uf.p * 1e6).round(2)
    uf["empresas_vigentes"] = uf.uf.map(local[local.empresa & local.vigente].groupby("uf").doc.nunique()).fillna(0).astype(int)
    resumo["by_uf"] = uf.rename(columns={"p": "populacao", "ESTADUAL": "estadual", "MUNICIPAL": "municipal"}).sort_values("uf").to_dict("records")

    bodies = s.groupby(["orgao", "esfera", "uf", "lista"]).agg(n=("codigo", "size"), empresas=("empresa", "sum"),
                                                               vigentes=("vigente", "sum")).reset_index()
    bodies = bodies.sort_values(["n", "orgao"], ascending=[False, True]).head(120)
    resumo["bodies"] = bodies.to_dict("records")

    ref = _read(src / "ref" / "fundamentacoes.csv")
    texts = dict(zip(ref.id, ref.texto)) if len(ref) else {}
    full = s.fundamentacao.map(texts).fillna("")
    s["lei"], s["artigo"] = full.map(law), full.map(article)
    laws = s[s.lei != ""].groupby("lei").agg(n=("codigo", "size"), empresas=("empresa", "sum")).reset_index()
    laws["label"] = laws.lei.map(LAWS).fillna(laws.lei.str.title())
    resumo["laws"] = laws.sort_values(["n", "lei"], ascending=[False, True]).head(14).to_dict("records")
    arts = s[s.artigo != ""].groupby(["artigo", "lei"]).size().rename("n").reset_index()
    resumo["articles"] = arts.sort_values(["n", "artigo"], ascending=[False, True]).head(20).to_dict("records")
    resumo["scope"] = s.groupby(["lista", "abrangencia"]).size().rename("n").reset_index().to_dict("records")
    resumo["origin"] = (s.groupby("origem").size().rename("n").reset_index()
                        .sort_values(["n", "origem"], ascending=[False, True]).head(12).to_dict("records"))

    # How long sanctions last, and how long they take to reach the list.
    years = (pd.to_datetime(s.fim, errors="coerce") - pd.to_datetime(s.inicio, errors="coerce")).dt.days / 365.25
    groups = {"Impedimento": "Barred from contracting", "Declaração de Inidoneidade": "Declared unfit (inidoneidade)",
              "Suspensão": "Suspended"}
    s["grupo"] = s.categoria.map(lambda c: next((v for k, v in groups.items() if c.startswith(k)), "Other"))
    yedges = [i / 4 for i in range(0, 41)] + [100]
    resumo["duration"] = {"edges": yedges, "groups": [
        {"grupo": g, "sem_prazo": int((t.fim == "").sum()), "hist": _hist(years[t.index], yedges), **_quant(years[t.index])}
        for g, t in s.groupby("grupo")]}
    lag = (pd.to_datetime(s.origem_data, errors="coerce") - pd.to_datetime(s.inicio, errors="coerce")).dt.days
    ledges = [-60, 0, *range(30, 750, 30), 100000]
    resumo["lag"] = {"edges": ledges, "spheres": [
        {"esfera": e, "hist": _hist(lag[t.index], ledges), **_quant(lag[t.index])}
        for e, t in s[s.esfera.isin(SPHERES)].groupby("esfera")]}

    # Companies on several lists, from several bodies.
    per = comp.groupby("doc").agg(n=("codigo", "size"))
    counts = per.n.clip(upper=10).value_counts().sort_index()
    resumo["repeat"] = [{"n": int(k), "empresas": int(v)} for k, v in counts.items()]

    fines = s[s.multa > 0]
    resumo["fines"] = {
        "by_year": fines.assign(ano=fines.inicio.str[:4]).groupby("ano").agg(n=("codigo", "size"), total=("multa", "sum")).reset_index().to_dict("records"),
        "by_sphere": fines.groupby("esfera").agg(n=("codigo", "size"), total=("multa", "sum")).reset_index().to_dict("records"),
        "by_body": fines.groupby("orgao").agg(n=("codigo", "size"), total=("multa", "sum")).reset_index()
        .sort_values(["total", "orgao"], ascending=[False, True]).head(15).to_dict("records"),
        "log_edges": [i / 2 for i in range(0, 21)],
        "log_hist": _hist(np.log10(fines.multa), [i / 2 for i in range(0, 21)]),
        **_quant(fines.multa),
    }

    if len(cep):
        resumo["cepim"] = {
            "orgaos": cep.groupby("orgao_concedente").agg(n=("numero_convenio", "size"), entidades=("cnpj_entidade", "nunique"))
            .reset_index().sort_values(["n", "orgao_concedente"], ascending=[False, True]).head(15).to_dict("records"),
            "motivos": cep.groupby("motivo_do_impedimento").size().rename("n").reset_index()
            .sort_values(["n", "motivo_do_impedimento"], ascending=[False, True]).head(12).to_dict("records"),
        }
    resumo["leniency"] = {
        "by_year": le.assign(ano=le.inicio.str[:4]).groupby("ano").size().rename("n").reset_index().to_dict("records") if len(le) else [],
        "status": le.situacao.value_counts().rename_axis("situacao").reset_index(name="n").to_dict("records") if len(le) else [],
        "effects": (_read(src / "leniencia_efeitos.csv").groupby("efeito_do_acordo_de_leniencia").id_do_acordo.nunique()
                    .rename("n").rename_axis("efeito").reset_index().sort_values(["n", "efeito"], ascending=[False, True])
                    .to_dict("records")) if (src / "leniencia_efeitos.csv").exists() else [],
        "brl_total": float(le[le.moeda == "BRL"].valor_total.sum()) if len(le) else 0.0,
        "brl_multa": float(le[le.moeda == "BRL"].multa.fillna(0).sum()) if len(le) else 0.0,
    }

    # Public money.
    cep_set = set(cep.get("cnpj_entidade", []))
    pd_ = pay.assign(cepim=pay.favorecido.isin(cep_set))
    by_year = pd_[pd_.barrado != ""].groupby(["ano", "barrado"]).valor.sum().unstack(fill_value=0.0)
    by_year = by_year.reindex(columns=["sim", "possivel", "nao"], fill_value=0.0).reset_index()
    sig = sanc_c.assign(v=_money(sanc_c.valor_global)) if len(sanc_c) else pd.DataFrame(columns=["cobre", "fornecedor", "v"])
    dias = _read(data / "pncp" / "dias.csv")
    resumo["money"] = {
        "pncp": {"by_cobre": sig.groupby("cobre").agg(contratos=("v", "size"), empresas=("fornecedor", "nunique"), valor=("v", "sum"))
                 .reset_index().to_dict("records"),
                 "days_read": len(dias), "first_day": dias.dia.min() if len(dias) else "", "last_day": dias.dia.max() if len(dias) else ""},
        "emendas": {"by_year": by_year.to_dict("records"),
                    "total": float(pay.valor.sum()), "barrado": float(pay[pay.barrado != ""].valor.sum()),
                    "barrado_sim": float(pay[pay.barrado == "sim"].valor.sum()),
                    "empresas": int(pay.favorecido.nunique()), "empresas_barrado": int(pay[pay.barrado != ""].favorecido.nunique()),
                    "first": pay.ano_mes.min() if len(pay) else "", "last": pay.ano_mes.max() if len(pay) else ""},
        "cepim": {"by_year": pd_[pd_.cepim].groupby("ano").agg(valor=("valor", "sum"), entidades=("favorecido", "nunique")).reset_index().to_dict("records"),
                  "total": float(pd_[pd_.cepim].valor.sum()), "entidades": int(pd_[pd_.cepim].favorecido.nunique())},
        "tse": [{"ano": y, "fornecedores": int(len(t)), "total": float(t.total.sum()),
                 "sancionados": int((t.barrado != "").sum()), "sancionados_total": float(t[t.barrado != ""].total.sum())}
                for y, t in tse.groupby("ano")],
    }
    flag = sig[sig.cobre.isin(["sim", "possivel"])] if len(sig) else sig
    fcols_ = ["assinatura", "orgao", "uf", "fornecedor", "fornecedor_nome", "objeto", "v", "cobre", "categoria_sancao", "orgao_sancionador"]
    resumo["money"]["pncp"]["flagged"] = (flag[fcols_].rename(columns={"v": "valor_global"})
                                          .sort_values(["valor_global", "assinatura"], ascending=[False, True]).head(300)
                                          .to_dict("records")) if len(flag) else []
    resumo["money"]["tse_list"] = (tse[tse.barrado != ""][["ano", "cnpj", "nome", "total", "n_candidatos"]]
                                   .sort_values(["ano", "total", "cnpj"], ascending=[True, False, True]).to_dict("records"))
    resumo["changes"] = {"rows": len(changes), "first": changes.data.min() if len(changes) else "",
                         "last": changes.data.max() if len(changes) else ""}

    # ---------------------------------------------------------- per company

    comp = s[s.empresa]

    names = pd.concat([comp[["doc", "nome"]],
                       cep.rename(columns={"cnpj_entidade": "doc", "nome_entidade": "nome"})[["doc", "nome"]] if len(cep) else None,
                       pd.DataFrame([(c, n) for cs, ns in zip(le.cnpjs, le.empresas) for c, n in zip(cs.split(), ns.split("; "))],
                                    columns=["doc", "nome"])])
    names = names[names.nome != ""].drop_duplicates("doc").set_index("doc").nome
    idx = pd.DataFrame(index=sorted(cnpjs))
    idx.index.name = "cnpj"
    idx["nome"] = names.reindex(idx.index).fillna("")
    g = comp.groupby("doc")
    by_list = comp.groupby(["doc", "lista"]).size().unstack(fill_value=0).reindex(columns=["CEIS", "CNEP"], fill_value=0)
    idx["ceis"] = by_list.CEIS.reindex(idx.index).fillna(0).astype(int)
    idx["cnep"] = by_list.CNEP.reindex(idx.index).fillna(0).astype(int)
    idx["cepim"] = cep.groupby("cnpj_entidade").size().reindex(idx.index).fillna(0).astype(int) if len(cep) else 0
    lcount = pd.Series([c for x in le.cnpjs for c in x.split()]).value_counts() if len(le) else pd.Series(dtype=int)
    idx["leniencia"] = lcount.reindex(idx.index).fillna(0).astype(int)
    idx["vigentes"] = g.vigente.sum().reindex(idx.index).fillna(0).astype(int)
    idx["barra"] = comp.assign(vb=comp.vigente & comp.bars).groupby("doc").vb.any().reindex(idx.index).fillna(False).astype(int)
    idx["orgaos"] = g.orgao.nunique().reindex(idx.index).fillna(0).astype(int)
    idx["ufs"] = g.uf.agg(lambda u: u[u != ""].nunique()).reindex(idx.index).fillna(0).astype(int)
    idx["primeira"] = g.inicio.min().reindex(idx.index).fillna("")
    idx["ultima"] = g.inicio.max().reindex(idx.index).fillna("")
    idx["multa"] = g.multa.sum().reindex(idx.index).fillna(0.0).round(2)
    cg = contracts.groupby("fornecedor")
    idx["contratos"] = cg.size().reindex(idx.index).fillna(0).astype(int)
    barred_c = contracts[contracts.cobre != ""]
    idx["contratos_sancionada"] = barred_c.groupby("fornecedor").size().reindex(idx.index).fillna(0).astype(int)
    idx["contratos_sancionada_valor"] = barred_c.groupby("fornecedor").valor_global.sum().reindex(idx.index).fillna(0.0).round(2)
    idx["emendas"] = pay.groupby("favorecido").valor.sum().reindex(idx.index).fillna(0.0).round(2)
    idx["emendas_sancionada"] = pay[pay.barrado != ""].groupby("favorecido").valor.sum().reindex(idx.index).fillna(0.0).round(2)
    idx["campanhas"] = tse_s.groupby("cnpj").total.sum().reindex(idx.index).fillna(0.0).round(2)
    csv(idx.reset_index(), out / "empresas.csv")

    shard_dir = out / "empresas"
    shard_dir.mkdir(parents=True, exist_ok=True)
    detail: dict[str, dict] = {}
    scols = ["lista", "codigo", "categoria", "inicio", "fim", "orgao", "esfera", "uf", "abrangencia", "multa", "processo", "artigo"]
    for doc, t in comp.sort_values(["doc", "inicio", "lista", "codigo"]).groupby("doc"):
        detail.setdefault(doc, {})["s"] = t[scols].values.tolist()
    for doc, t in contracts.sort_values(["fornecedor", "assinatura", "controle"]).groupby("fornecedor"):
        detail.setdefault(doc, {})["c"] = t[["assinatura", "orgao", "esfera", "uf", "objeto", "valor_global", "cobre", "controle"]].values.tolist()
    py = (pay.assign(total=pay.valor, sancionada=pay.valor.where(pay.barrado != "", 0.0), sim=pay.valor.where(pay.barrado == "sim", 0.0))
          .groupby(["favorecido", "ano"], as_index=False)[["total", "sancionada", "sim"]].sum())
    for doc, t in py.groupby("favorecido"):
        detail.setdefault(doc, {})["e"] = t[["ano", "total", "sancionada", "sim"]].values.tolist()
    for doc, t in tse_s.sort_values(["cnpj", "ano"]).groupby("cnpj"):
        detail.setdefault(doc, {})["t"] = t[["ano", "total", "n_candidatos", "barrado"]].values.tolist()
    pa = pay.merge(em[["codigo", "autor_codigo", "autor", "partido", "uf"]], left_on="codigo_emenda", right_on="codigo")
    pa = pa.assign(sanc=pa.valor.where(pa.barrado != "", 0.0)).groupby(["favorecido", "autor_codigo", "autor", "partido", "uf"], as_index=False)[["valor", "sanc"]].sum()
    for doc, t in pa.sort_values(["favorecido", "valor", "autor_codigo"], ascending=[True, False, True]).groupby("favorecido"):
        detail.setdefault(doc, {})["a"] = t[["autor", "partido", "uf", "valor", "sanc"]].values.tolist()
    if len(cep):
        for doc, t in cep.sort_values(["cnpj_entidade", "numero_convenio"]).groupby("cnpj_entidade"):
            detail.setdefault(doc, {})["p"] = t[["numero_convenio", "orgao_concedente", "motivo_do_impedimento"]].values.tolist()
    for _, r in le.iterrows():
        for c in r.cnpjs.split():
            detail.setdefault(c, {}).setdefault("l", []).append(r.id)
    shards: dict[str, dict] = {}
    for doc in sorted(detail):
        shards.setdefault(doc[:2], {})[doc] = detail[doc]
    keep = set()
    for k, v in shards.items():
        p = shard_dir / f"{k}.json"
        write_json(v, p, digits=2)
        keep.add(p.name)
    for p in shard_dir.glob("*.json"):
        if p.name not in keep:
            p.unlink()

    # ---------------------------------------------------------- tables

    fcols = ["inicio", "doc", "nome", "categoria", "multa", "orgao", "esfera", "uf", "processo"]
    csv(fines[fines.empresa][fcols].rename(columns={"doc": "cnpj"}).sort_values(["multa", "cnpj", "inicio"], ascending=[False, True, True]),
        out / "multas.csv")
    csv(le.sort_values("id"), out / "leniencia.csv")
    end = (pd.Timestamp(day) + pd.Timedelta(days=SOON)).strftime("%Y-%m-%d") if day else ""
    soon = comp[(comp.fim > day) & (comp.fim <= end)] if day else comp.iloc[:0]
    csv(soon[["fim", "doc", "nome", "lista", "categoria", "orgao", "esfera", "uf"]].rename(columns={"doc": "cnpj"})
        .sort_values(["fim", "cnpj", "lista"]), out / "expirando.csv")
    resumo["tiles"]["expirando"] = int(len(soon))
    resumo["tiles"]["expirando_pessoas"] = int(((s.tipo == "F") & (s.fim > day) & (s.fim <= end)).sum()) if day else 0

    if len(changes):
        m = changes.assign(kind=np.where(changes.documento.str.fullmatch(COMPANY) & (changes.tipo_de_pessoa != "F"), "empresa", "pessoa"))
        csv(m.groupby(["data", "lista", "mudanca", "kind"]).size().rename("n").reset_index().sort_values(["data", "lista", "mudanca", "kind"]),
            out / "mudancas.csv")
        recent = m[m.kind == "empresa"].sort_values(["data", "lista", "codigo"], ascending=[False, True, True]).head(RECENT)
        csv(recent[["data", "lista", "codigo", "mudanca", "documento", "nome"]].rename(columns={"documento": "cnpj"}), out / "recentes.csv")
    else:
        csv(pd.DataFrame(columns=["data", "lista", "mudanca", "kind", "n"]), out / "mudancas.csv")
        csv(pd.DataFrame(columns=["data", "lista", "codigo", "mudanca", "cnpj", "nome"]), out / "recentes.csv")

    csv(au[["autor_codigo", "autor", "kind", "pessoa", "partido", "uf", "primeiro", "ultimo", "emendas", "pago_total",
            "pago_sancionadas", "pago_sim", "share", "empresas_sancionadas"]].sort_values("autor_codigo"), out / "autores.csv")
    csv(pt.sort_values("partido"), out / "partidos.csv")
    csv(by_party_year.round(2).sort_values(["partido", "ano"]), out / "partidos_ano.csv")
    resumo["authors"] = {
        "with_payments": int(len(au)), "with_barred": int((au.pago_sancionadas > 0).sum()),
        "individual_per_million": float(1e6 * ind.pago_sancionadas.sum() / ind.pago.sum()) if ind.pago.sum() else None,
        "individual_sim_per_million": float(1e6 * ind.pago_sim.sum() / ind.pago.sum()) if ind.pago.sum() else None,
        "by_kind": au.groupby("kind").agg(autores=("autor_codigo", "size"), pago_total=("pago_total", "sum"),
                                          pago_sancionadas=("pago_sancionadas", "sum")).reset_index().to_dict("records"),
        "unattributed": float(pay[pay.codigo_emenda == ""].valor.sum()) if len(pay) else 0.0,
    }
    write_json(resumo, out / "resumo.json", digits=2)
    return {"snapshot": day, "companies": len(idx), "shards": len(shards), "amendment_payments": len(pay),
            "contracts": len(contracts)}
