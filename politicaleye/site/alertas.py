"""Summaries for the red-flags page: ``data/site/alertas/``.

Patterns across the open data that are worth a closer look. A flag is not evidence of an irregularity:
each table says the rule that raised it and what it is measured against, and the page lists the usual
innocent explanations. People are never named; companies whose name is a person's (individual firms) are
counted with their name withheld, as on the sanctions page.

    resumo.json               per flag: how many cases, how much money, the thresholds used
    emendas_impedidas.csv     amendment money paid to a company while it was barred (CEIS/CNEP), by author
    contratos_impedidas.csv   contracts signed with a company barred at the time, the bar covering the buyer
    campanha_emendas.csv      a deputy's campaign supplier later paid from that deputy's own amendments
    concentracao.csv          a deputy's amendment money concentrated on one private recipient
    fornecedor_dominante.csv  public buyers where one supplier took most of their large contracts
    leniencia_contratos.csv   companies with a leniency agreement and contracts signed after it
    entidades.csv             companies on two lists or more
    parlamentares.csv         deputies on two lists or more

See methodology/alertas.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..views.deputados import election_of
from .common import csv, write_json
from .pncp import plausible, read_sanctioned, town_revenue
from .sancoes import individual_firm, name_tokens, party_timeline

# Thresholds (see methodology/alertas.md for why each one).
CONC_MIN = 1_000_000      # a private recipient took at least this much of a deputy's amendment money...
CONC_SHARE = 0.25         # ...and at least this share of it
CONC_SINCE = "2019-02"    # payments since the 56th legislature began
CAMPAIGN_MIN = 10_000     # amendment money paid to a deputy's own campaign supplier
DOM_CONTRACTS, DOM_VALUE, DOM_SHARE = 5, 10_000_000, 0.8   # a buyer's large contracts, and the top supplier's share
LEGS = (57, 56)
# Recipients that are governments, public bodies, state companies or banks are not "private": money reaches
# them by design (town halls, health funds, the banks that carry transfers).
PRIVATE = {"Associação Privada", "Fundação Privada", "Organização Religiosa", "Cooperativa", "Sociedade Empresária Limitada",
           "Sociedade Anônima Fechada", "Sociedade Anônima Aberta", "Sociedade Simples Limitada", "Sociedade Simples Pura",
           "Empresário (Individual)", "Empresa Individual de Responsabilidade Limitada (de Natureza Empresária)",
           "Sociedade Empresária em Nome Coletivo", "Entidade Sindical", "Partido Político", "Serviço Notarial e Registral (Cartório)"}
INDIVIDUAL = {"Empresário (Individual)", "Empresa Individual de Responsabilidade Limitada (de Natureza Empresária)"}
# Kinds of private recipient that routinely execute amendments: support foundations of public universities
# and research bodies, and charity hospitals. Tagged so the page can tell them apart, never dropped.
SUPPORT = re.compile(r"\bFUNDA[CÇ][AÃ]O\b.*\b(APOIO|AMPARO|DESENVOLVIMENTO|PESQUISA|ENSINO|TECNOL|FACULDADE|UNIVERSI)|FIOTEC|COPPETEC|FINATEC|FUNDEP\b|FADESP|FAURGS|FUNCAMP|FAPEU|FAPEX|FUNPEC")
# Regulated public services: a campaign pays their bills and so do public bodies, so a match means nothing.
UTILITY = re.compile(r"ENERGIA|ELETRIC|ELETRO|DISTRIBUI[CÇ][AÃ]O|SANEAMENTO|[AÁ]GUAS? E ESGOTO|TELEF[OÔ]NI|TELECOM|CORREIOS|"
                     r"\b(?:CEMIG|COPEL|CELESC|CPFL|LIGHT|ENEL|EQUATORIAL|NEOENERGIA|COELBA|CELPE|COSERN|ELEKTRO|SABESP|COPASA|CAGECE|EMBASA|COMPESA|SANEPAR|CEDAE|CLARO|VIVO|TIM|OI)\b")
HEALTH = re.compile(r"SANTA CASA|HOSPITAL|BENEFIC[EÊ]NCIA|MISERIC[OÓ]RDIA|\bAPAE\b|PESTALOZZI|ONCOL|C[AÂ]NCER")


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def _money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def display(name: str) -> str:
    """Names the amendments table writes in capitals, in title case (prepositions kept small)."""
    if not name or name != name.upper():
        return name
    small = {"DA", "DE", "DO", "DAS", "DOS", "E"}
    return " ".join(w.lower() if w in small and i else w.capitalize() for i, w in enumerate(name.split()))


def kind_of(nome: str, natureza: str) -> str:
    if natureza in INDIVIDUAL or natureza.startswith("Sociedade") or natureza == "Cooperativa":
        return "empresa"
    if SUPPORT.search(nome):
        return "fundacao_apoio"
    if HEALTH.search(nome):
        return "saude"
    return "entidade"


def deputies(data: Path) -> pd.DataFrame:
    """Every deputy of the legislatures covered, once (the latest legislature wins): pessoa, id, name, party, state."""
    parts = []
    for leg in LEGS:
        v = _read(data / "views" / f"deputados_{leg}.csv")
        if len(v):
            parts.append(v.assign(leg=leg)[["pessoa", "deputado_id", "nome", "partido", "uf", "leg", "campanha_sq_candidato"]])
    if not parts:
        return pd.DataFrame(columns=["pessoa", "deputado_id", "nome", "partido", "uf", "leg", "campanha_sq_candidato"])
    return pd.concat(parts, ignore_index=True)


def members(data: Path, deps: pd.DataFrame) -> pd.DataFrame:
    """Every member of Congress the crosswalk knows: name, Câmara and Senate ids, latest party, state and house.
    Deputies of the legislatures covered take their view's row; anyone else (senators, earlier deputies) their
    latest month in either house."""
    x = _read(data / "ref" / "politicians.csv")
    if not len(x):
        return pd.DataFrame(columns=["deputado_id", "senador_id", "nome", "partido", "uf", "casa", "leg"])
    ids = x.pivot_table(index="pessoa", columns="fonte", values="id", aggfunc="first")
    nm = x.assign(o=x.fonte.map({"camara": 0, "senado": 1}).fillna(2)).sort_values("o").drop_duplicates("pessoa").set_index("pessoa").nome
    tl = party_timeline(data).sort_values("month").drop_duplicates("pessoa", keep="last").set_index("pessoa")
    m = pd.DataFrame({"deputado_id": ids.get("camara", pd.Series(dtype=str)), "senador_id": ids.get("senado", pd.Series(dtype=str))}).reindex(nm.index)
    m = m.assign(nome=nm, partido=tl.partido.reindex(nm.index), uf=tl.uf.reindex(nm.index), casa=tl.casa.reindex(nm.index), leg=0).fillna("")
    d = deps.drop_duplicates("pessoa").set_index("pessoa")
    m.loc[d.index.intersection(m.index), ["nome", "partido", "uf", "leg"]] = d[["nome", "partido", "uf", "leg"]]
    m.loc[d.index.intersection(m.index), "casa"] = "camara"
    m["leg"] = m.leg.astype(int)
    m["nome"] = m.nome.map(display)
    return m


def payments_by_author(data: Path) -> pd.DataFrame:
    """Every amendment payment whose author is a known person: pessoa, recipient, month, value."""
    x = _read(data / "ref" / "politicians.csv")
    who = x[x.fonte == "emendas"].drop_duplicates("id").set_index("id").pessoa if len(x) else pd.Series(dtype=str)
    em = pd.concat([pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo", "autor_codigo"])
                    for p in sorted((data / "emendas" / "emendas").glob("*.csv"))], ignore_index=True).drop_duplicates("codigo")
    owner = em.assign(pessoa=em.autor_codigo.map(who)).dropna(subset=["pessoa"]).set_index("codigo").pessoa
    out = []
    for p in sorted((data / "emendas" / "pagamentos").glob("*.csv")):
        t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo_emenda", "ano_mes", "favorecido", "valor"])
        t = t[t.codigo_emenda.isin(owner.index) & (t.favorecido != "")]
        out.append(t.assign(pessoa=t.codigo_emenda.map(owner), valor=_money(t.valor)))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["codigo_emenda", "ano_mes", "favorecido", "valor", "pessoa"])


def build(data: Path) -> dict:
    out = data / "site" / "alertas"
    people = name_tokens(data)
    fav = _read(data / "emendas" / "favorecidos.csv")
    fav = fav.drop_duplicates("favorecido").set_index("favorecido") if len(fav) else pd.DataFrame(columns=["nome", "natureza_juridica"])
    deps = deputies(data)
    dep_of = members(data, deps)

    def name_of(cnpj: pd.Series, nome: pd.Series, natureza: pd.Series | None = None) -> tuple[pd.Series, pd.Series]:
        """A company's name, withheld (and flagged) when it is an individual firm named after a person."""
        nat = natureza if natureza is not None else cnpj.map(fav.natureza_juridica).fillna("") if len(fav) else pd.Series("", index=cnpj.index)
        hidden = individual_firm(nome, people) | nat.isin(INDIVIDUAL) | cnpj.str.contains(r"\*", regex=True)   # a masked CPF is a person
        return nome.where(~hidden, ""), hidden.astype(int)

    def who(pessoa: pd.Series) -> pd.DataFrame:
        d = dep_of.reindex(pessoa.values)
        return pd.DataFrame({"deputado_id": d.deputado_id.fillna("").values, "senador_id": d.senador_id.fillna("").values, "deputado": d.nome.fillna("").values,
                             "partido": d.partido.fillna("").values, "uf": d.uf.fillna("").values, "casa": d.casa.fillna("").values,
                             "leg": d.leg.fillna(0).astype(int).values}, index=pessoa.index)

    r: dict = {"rules": {"conc_min": CONC_MIN, "conc_share": CONC_SHARE, "conc_since": CONC_SINCE, "campaign_min": CAMPAIGN_MIN,
                         "dom_contracts": DOM_CONTRACTS, "dom_value": DOM_VALUE, "dom_share": DOM_SHARE}}

    # ---------------------------------------------------------- 1. amendments paid while barred
    ei = _read(data / "site" / "sancoes" / "emendas_impedidas.csv")
    emp = _read(data / "site" / "sancoes" / "empresas.csv")
    names = emp.set_index("cnpj").nome if len(emp) else pd.Series(dtype=str)
    if len(ei):
        ei = ei.assign(valor=_money(ei.valor), pagamentos=pd.to_numeric(ei.pagamentos))
        ei["nome"], ei["pf"] = name_of(ei.favorecido, ei.favorecido.map(names).fillna(""))
        d = who(ei.pessoa)
        ei = pd.concat([ei, d], axis=1)
        ei["autor"] = ei.deputado.where(ei.deputado != "", ei.autor)
        ei = ei.rename(columns={"favorecido": "cnpj"})[["cnpj", "nome", "pf", "pessoa", "deputado_id", "senador_id", "casa", "leg", "autor", "tipo", "partido", "uf", "barrado", "valor", "pagamentos", "primeiro", "ultimo"]]
        ei = ei.sort_values(["valor", "cnpj", "autor"], ascending=[False, True, True])
    else:
        ei = pd.DataFrame(columns=["cnpj", "nome", "pf", "pessoa", "deputado_id", "senador_id", "casa", "leg", "autor", "tipo", "partido", "uf", "barrado", "valor", "pagamentos", "primeiro", "ultimo"])
    # A bar limited to another state's or a town's bodies does not stop federal money: counted, not listed.
    nao = ei[ei.barrado == "nao"]
    ei = ei[ei.barrado.isin(["sim", "possivel"])]
    csv(ei.round(2), out / "emendas_impedidas.csv")
    sim = ei[ei.barrado == "sim"]
    r["emendas_impedidas"] = {"casos": len(ei), "empresas": int(ei.cnpj.nunique()), "autores": int(ei.autor.nunique()), "valor": float(ei.valor.sum()),
                              "sim": {"casos": len(sim), "empresas": int(sim.cnpj.nunique()), "valor": float(sim.valor.sum())},
                              "fora_do_alcance": {"casos": len(nao), "valor": float(nao.valor.sum())}}

    # ---------------------------------------------------------- 2. contracts signed with a barred company
    rcl = town_revenue(data)
    cs = read_sanctioned(data / "pncp")
    if len(cs):
        cs = plausible(cs, rcl)
        cs = cs[(cs.suspeito != 2) & (cs.cobre == "sim") & cs.fornecedor.str.fullmatch(r"\d{14}")].drop_duplicates("controle")
        cs["nome"], cs["pf"] = name_of(cs.fornecedor, cs.fornecedor_nome, pd.Series("", index=cs.index))
        cs = cs.assign(valor=cs.v, objeto=cs.objeto.str.slice(0, 160))
        cols = ["controle", "assinatura", "orgao", "esfera", "uf", "fornecedor", "nome", "pf", "objeto", "valor", "categoria_sancao", "sancao_inicio", "sancao_fim", "orgao_sancionador"]
        cs = cs[cols].rename(columns={"fornecedor": "cnpj"}).sort_values(["valor", "controle"], ascending=[False, True])
    else:
        cs = pd.DataFrame(columns=["controle", "assinatura", "orgao", "esfera", "uf", "cnpj", "nome", "pf", "objeto", "valor", "categoria_sancao", "sancao_inicio", "sancao_fim", "orgao_sancionador"])
    csv(cs.round(2), out / "contratos_impedidas.csv")
    dias = _read(data / "pncp" / "dias.csv")
    r["contratos_impedidas"] = {"casos": len(cs), "empresas": int(cs.cnpj.nunique()), "valor": float(cs.valor.sum()), "dias_lidos": len(dias)}

    # ---------------------------------------------------------- 3 and 4: amendments by author
    pay = payments_by_author(data)
    pay["natureza"] = pay.favorecido.map(fav.natureza_juridica).fillna("") if len(fav) else ""
    pay["fav_nome"] = pay.favorecido.map(fav.nome).fillna("") if len(fav) else ""
    pay = pay[pay.pessoa.isin(dep_of.index)]

    # 3. a campaign supplier later paid from the same deputy's amendments
    rows = []
    for leg in LEGS:
        y = election_of(leg)
        fc = _read(data / "tse" / str(y) / "fornecedores_candidatos.csv")
        v = deps[(deps.leg == leg) & (deps.campanha_sq_candidato != "")]
        if not len(fc) or not len(v):
            continue
        sq = v.set_index("campanha_sq_candidato").pessoa
        fc = fc[fc.sq_candidato.isin(sq.index)].assign(pessoa=lambda t: t.sq_candidato.map(sq), campanha=lambda t: _money(t.valor))
        after = pay[(pay.ano_mes >= f"{y}-10") & pay.natureza.isin(PRIVATE) & ~pay.fav_nome.str.contains(UTILITY)]
        m = after.merge(fc[["pessoa", "cnpj", "campanha"]], left_on=["pessoa", "favorecido"], right_on=["pessoa", "cnpj"])
        g = m.groupby(["pessoa", "favorecido", "fav_nome", "natureza"], as_index=False).agg(
            emendas=("valor", "sum"), pagamentos=("valor", "size"), primeiro=("ano_mes", "min"), ultimo=("ano_mes", "max"), campanha=("campanha", "first"))
        rows.append(g.assign(eleicao=y))
    ce = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["pessoa", "favorecido", "fav_nome", "natureza", "emendas", "pagamentos", "primeiro", "ultimo", "campanha", "eleicao"])
    ce = ce[ce.emendas >= CAMPAIGN_MIN].drop_duplicates(["pessoa", "favorecido"])
    ce["nome"], ce["pf"] = name_of(ce.favorecido, ce.fav_nome, ce.natureza)
    ce = pd.concat([ce, who(ce.pessoa)], axis=1).rename(columns={"favorecido": "cnpj"})
    ce = ce[["pessoa", "deputado_id", "senador_id", "casa", "deputado", "partido", "uf", "leg", "cnpj", "nome", "pf", "natureza", "eleicao", "campanha", "emendas", "pagamentos", "primeiro", "ultimo"]]
    ce = ce.sort_values(["emendas", "pessoa", "cnpj"], ascending=[False, True, True])
    csv(ce.round(2), out / "campanha_emendas.csv")
    n_sup = sum(len(_read(data / "tse" / str(election_of(l)) / "fornecedores_candidatos.csv")) for l in LEGS)
    r["campanha_emendas"] = {"casos": len(ce), "deputados": int(ce.pessoa.nunique()), "valor": float(ce.emendas.sum()), "pares_campanha": n_sup}

    # 4. a deputy's amendment money concentrated on one private recipient
    since = pay[pay.ano_mes >= CONC_SINCE]
    tot = since.groupby("pessoa").valor.sum()
    pr = since[since.natureza.isin(PRIVATE)].groupby(["pessoa", "favorecido", "fav_nome", "natureza"], as_index=False).agg(
        valor=("valor", "sum"), pagamentos=("valor", "size"), primeiro=("ano_mes", "min"), ultimo=("ano_mes", "max"))
    pr["total_deputado"] = pr.pessoa.map(tot)
    pr["share"] = pr.valor / pr.total_deputado
    # The baseline: across every deputy and private recipient, how large the largest share usually is.
    top = pr.sort_values("share", ascending=False).drop_duplicates("pessoa")
    co = pr[(pr.valor >= CONC_MIN) & (pr.share >= CONC_SHARE)].copy()
    co["tipo"] = [kind_of(n, nat) for n, nat in zip(co.fav_nome, co.natureza)]
    co["nome"], co["pf"] = name_of(co.favorecido, co.fav_nome, co.natureza)
    co = pd.concat([co, who(co.pessoa)], axis=1).rename(columns={"favorecido": "cnpj"})
    co = co[["pessoa", "deputado_id", "senador_id", "casa", "deputado", "partido", "uf", "leg", "cnpj", "nome", "pf", "natureza", "tipo", "valor", "total_deputado", "share", "pagamentos", "primeiro", "ultimo"]]
    co = co.sort_values(["share", "pessoa"], ascending=[False, True])
    csv(co.round(4), out / "concentracao.csv")
    r["concentracao"] = {"casos": len(co), "deputados": int(co.pessoa.nunique()), "valor": float(co.valor.sum()),
                         "por_tipo": co.groupby("tipo").size().to_dict(),
                         "base": {"deputados": int(len(top)), "mediana_maior_share": float(top.share.median()) if len(top) else None,
                                  "p90_maior_share": float(top.share.quantile(0.9)) if len(top) else None}}

    # ---------------------------------------------------------- 5. a buyer dominated by one supplier
    org = _read(data / "site" / "pncp" / "orgaos.csv")
    if len(org):
        for c in ("contratos", "valor", "maior_share", "hhi", "fornecedores"):
            org[c] = pd.to_numeric(org[c], errors="coerce")
        dom = org[(org.contratos >= DOM_CONTRACTS) & (org.valor >= DOM_VALUE) & (org.maior_share >= DOM_SHARE)].copy()
        dom["nome"], dom["pf"] = name_of(dom.maior_fornecedor, dom.maior_fornecedor_nome.fillna(""), pd.Series("", index=dom.index))
        dom = dom[["orgao_cnpj", "orgao", "esfera", "uf", "municipio_ibge", "contratos", "fornecedores", "valor", "maior_fornecedor", "nome", "pf", "maior_share", "hhi"]]
        dom = dom.rename(columns={"maior_fornecedor": "cnpj"}).sort_values(["valor", "orgao_cnpj"], ascending=[False, True])
        base = org[(org.contratos >= DOM_CONTRACTS)]
        r["fornecedor_dominante"] = {"casos": len(dom), "valor": float(dom.valor.sum()), "orgaos_com_5": int(len(base)),
                                     "mediana_maior_share": float(base.maior_share.median()) if len(base) else None, "dias_lidos": len(dias)}
    else:
        dom = pd.DataFrame(columns=["orgao_cnpj", "orgao", "esfera", "uf", "municipio_ibge", "contratos", "fornecedores", "valor", "cnpj", "nome", "pf", "maior_share", "hhi"])
        r["fornecedor_dominante"] = {"casos": 0, "valor": 0.0, "orgaos_com_5": 0, "mediana_maior_share": None, "dias_lidos": len(dias)}
    csv(dom.round(4), out / "fornecedor_dominante.csv")

    # ---------------------------------------------------------- 6. leniency, then new contracts
    le = _read(data / "sancoes" / "leniencia.csv")
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted((data / "pncp" / "contratos").glob("*.csv"))]
    big = plausible(pd.concat(parts, ignore_index=True).drop_duplicates("controle"), rcl) if parts else pd.DataFrame()
    if len(le) and len(big):
        le = le[le.cnpj_do_sancionado.str.fullmatch(r"\d{14}")]
        start = le.groupby("cnpj_do_sancionado").data_de_inicio_do_acordo.min()
        lc = big[big.fornecedor.isin(start.index) & (big.suspeito != 2)].copy()
        lc = lc[lc.assinatura >= lc.fornecedor.map(start)]
        lc = lc.assign(acordo=lc.fornecedor.map(start), valor=lc.v, objeto=lc.objeto.str.slice(0, 160))
        lc = lc[["controle", "assinatura", "orgao", "esfera", "uf", "fornecedor", "fornecedor_nome", "objeto", "valor", "acordo"]].rename(
            columns={"fornecedor": "cnpj", "fornecedor_nome": "nome"}).sort_values(["valor", "controle"], ascending=[False, True])
    else:
        lc = pd.DataFrame(columns=["controle", "assinatura", "orgao", "esfera", "uf", "cnpj", "nome", "objeto", "valor", "acordo"])
    csv(lc.round(2), out / "leniencia_contratos.csv")
    r["leniencia_contratos"] = {"casos": len(lc), "empresas": int(lc.cnpj.nunique()), "valor": float(lc.valor.sum()), "acordos": int(len(le)), "dias_lidos": len(dias)}

    # ---------------------------------------------------------- who is on more than one list
    lists = [("emendas_impedidas", ei[["cnpj", "nome", "pf"]]), ("contratos_impedidas", cs[["cnpj", "nome", "pf"]]),
             ("campanha_emendas", ce[["cnpj", "nome", "pf"]]), ("concentracao", co[["cnpj", "nome", "pf"]]),
             ("fornecedor_dominante", dom[["cnpj", "nome", "pf"]]), ("leniencia_contratos", lc[["cnpj", "nome"]].assign(pf=0))]
    al = pd.concat([t.assign(lista=k) for k, t in lists], ignore_index=True)
    al = al[al.cnpj != ""]
    ent = al.groupby("cnpj").agg(nome=("nome", "first"), pf=("pf", "max"), listas=("lista", lambda s: ";".join(sorted(set(s))))).reset_index()
    ent["n"] = ent.listas.str.count(";") + 1
    ent = ent[ent.n >= 2].sort_values(["n", "cnpj"], ascending=[False, True])
    csv(ent, out / "entidades.csv")
    dl = pd.concat([ei[ei.pessoa != ""][["pessoa"]].assign(lista="emendas_impedidas"), ce[["pessoa"]].assign(lista="campanha_emendas"),
                    co[["pessoa"]].assign(lista="concentracao")], ignore_index=True)
    dl = dl[dl.pessoa.isin(dep_of.index)]
    par = dl.groupby("pessoa").agg(listas=("lista", lambda s: ";".join(sorted(set(s))))).reset_index()
    par["n"] = par.listas.str.count(";") + 1
    par = pd.concat([par, who(par.pessoa)], axis=1)
    par = par[par.n >= 2][["pessoa", "deputado_id", "senador_id", "casa", "deputado", "partido", "uf", "leg", "listas", "n"]].sort_values(["n", "deputado"], ascending=[False, True])
    csv(par, out / "parlamentares.csv")
    r["cruzamentos"] = {"entidades": len(ent), "parlamentares": len(par)}

    write_json(r, out / "resumo.json", digits=4)
    return {k: v.get("casos") for k, v in r.items() if isinstance(v, dict) and "casos" in v} | r["cruzamentos"]
