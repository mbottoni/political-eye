"""Summaries for the company profiles page: ``data/site/empresas/``.

One profile per company or private organisation (CNPJ) that a source links to public money or to a sanction:

    resumo.json        how many companies each source contributes, each source's coverage (sanctions snapshot,
                       PNCP days read, amendment months, elections), the caps below
    indice.csv         one row per company, for the search box: name (blank for an individual firm), the
                       sources it appears in, and the public money it received
    destaques.csv      the companies found in the most sources and red-flag lists, for the page's list
    autores.csv        the amendment authors the profiles refer to: name, kind, party, state, deputy or senator id
    perfis/<nnn>.json  per CNPJ, sharded by its first three digits: its sanctions (in force, ended, removed from
                       the lists), the PNCP contracts it signed, the amendment money paid to it and whose
                       amendments paid it, what election campaigns paid it and which candidates, and the
                       red-flag lists it is on

Who is in: every CNPJ on the sanctions lists or their change log, every supplier of a large PNCP contract (or of
any contract signed while barred), every private recipient of amendment money, every campaign supplier the TSE
tables list (R$ 50,000 or more in an election), and every CNPJ on a red-flag list. Public bodies (towns, funds,
ministries, autarchies) are left out: they receive money by design. State companies stay, labelled.

People are never named: an individual firm (MEI, empresário individual, EIRELI or any name the sanctions page
reads as a person's) keeps its CNPJ and numbers but not its name. See methodology/empresas.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .alertas import INDIVIDUAL, deputies, display, members
from .common import csv, write_json
from .pncp import START, plausible, town_revenue
from .sancoes import ELECTIONS, _snapshot, federal_scope, in_force, individual_firm, name_tokens, sanctions, while_barred

CNPJ = r"\d{14}"
SHARD = 3            # a profile file holds the CNPJs that share their first SHARD digits
TOP_CONTRACTS = 10   # contracts listed in a profile (the largest); every one counts in its totals
TOP_BARRED = 15      # ...and up to this many of those signed while barred
TOP_BUYERS = 8
TOP_AUTHORS = 15     # amendment authors listed; the rest are summed
TOP_CANDIDATES = 10  # candidates listed per election; the rest are summed
FEATURED = 400       # rows of destaques.csv
OBJ = 70             # characters of a contract's object kept, after its boilerplate opening
# Legal natures of public bodies: governments, their funds, bodies, autarchies, public foundations and consortia.
PUBLIC = re.compile(r"^(Município|Estado ou Distrito Federal|Fundo Público|Órgão Público|Autarquia|Fundação Pública|Consórcio Público|União)")
STATE_CO = {"Empresa Pública", "Sociedade de Economia Mista"}
PERSONAL = INDIVIDUAL | {"Produtor Rural (Pessoa Física)", "Sociedade Unipessoal de Advogados"}
# The red-flag lists (data/site/alertas/) and the page tab that explains each.
FLAGS = ["emendas_impedidas", "contratos_impedidas", "campanha_emendas", "concentracao", "fornecedor_dominante", "leniencia_contratos"]
FEDERAL = {"Deputado Federal": "DF", "Senador": "SN", "1º Suplente": "S1", "2º Suplente": "S2"}
RESULT = {"ELEITO": "e", "ELEITO POR QP": "e", "ELEITO POR MÉDIA": "e", "SUPLENTE": "s", "NÃO ELEITO": "n"}


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def _money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _read_dir(folder: Path, **kw) -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False, **kw) for p in sorted(folder.glob("*.csv"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def sanctioned_contracts(src: Path) -> pd.DataFrame:
    """Contracts signed with a barred company: ``data/pncp/sancionados/`` by month, or the single file it replaced."""
    cols = ["controle", "publicacao", "assinatura", "orgao", "esfera", "uf", "municipio_ibge", "fornecedor", "objeto",
            "valor_inicial", "valor_global", "cobre"]
    files = sorted((src / "sancionados").glob("*.csv")) + [p for p in [src / "contratos_sancionados.csv"] if p.exists()]
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False, usecols=lambda c: c in cols) for p in files]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


def member_link(deputado_id: pd.Series, leg: pd.Series, senador_id: pd.Series) -> pd.Series:
    """Where the page can link a member of Congress: ``d57:204376`` (a deputy's profile on this site, in a
    legislature it covers), ``s:5672`` (the Senate's page) or ""."""
    d = "d" + leg.astype(str) + ":" + deputado_id
    s = "s:" + senador_id
    return d.where((deputado_id != "") & leg.astype(str).isin(["56", "57"]), s.where(senador_id != "", ""))


def whole(x):
    """Money in whole reais: every number of 100 or more loses its centavos (shares and small sums keep theirs)."""
    if isinstance(x, dict):
        return {k: whole(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [whole(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        x = x.item()
    if isinstance(x, float) and x == x and abs(x) >= 100:
        return int(round(x))
    return x


def lists(t: pd.DataFrame, key: str, cols: list[str]) -> dict:
    """``{key: [[col, ...], ...]}`` in the frame's row order (a groupby per company is too slow for 100,000 of them)."""
    out: dict = {}
    for k, *row in t[[key, *cols]].itertuples(index=False, name=None):
        out.setdefault(k, []).append(row)
    return out


RANK = {"sim": 3, "possivel": 2, "nao": 1, "": 0}


def best_scope(s: pd.Series) -> str:
    return max(s, key=lambda v: RANK.get(v, 0)) if len(s) else ""


# Openings that most contract objects share and that say nothing ("Contratação de empresa especializada para ...").
BOILERPLATE = re.compile(r"^\s*(?:\[LICITANET\]\s*-\s*)+|^(?:O )?OBJETO(?: DO PRESENTE| DESTE| DO| DA PRESENTE)? (?:INSTRUMENTO|CONTRATO|TERMO|AJUSTE)[^,]{0,20}? [EÉ] (?:A |O )?|"
                         r"^REGISTRO DE PRE[CÇ]OS? (?:PARA (?:A )?(?:FUTURAS? E EVENTUA(?:L|IS) )?)?|"
                         r"^CONTRATA[CÇ][AÃ]O (?:EMERGENCIAL )?DE (?:UMA )?(?:EMPRESAS?|PESSOAS? JUR[IÍ]DICAS?)(?: ESPECIALIZADAS?| DE ENGENHARIA)?"
                         r"(?: (?:PARA|EM|NA|NO|NOS|NAS|DE)(?: A| O| AS| OS)?)? ", re.I)


def short_object(text: pd.Series, limit: int = OBJ) -> pd.Series:
    """A contract's object without its boilerplate opening, cut at ``limit`` characters (the PNCP has the rest)."""
    def one(t: str) -> str:
        for _ in range(3):
            u = BOILERPLATE.sub("", t, count=1)
            if u == t or not u.strip():
                break
            t = u
        t = t.strip(" -:,")
        t = t[:1].upper() + t[1:]
        return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"
    return text.fillna("").map(one)


def scrub(text: pd.Series, names: pd.Series) -> pd.Series:
    """Take a withheld firm's name out of a free text (a contract's object can repeat the supplier's name)."""
    return pd.Series([t.replace(n, "…") if n and len(n) >= 6 else t for t, n in zip(text, names)], index=text.index)


def _ym_range(s: pd.Series) -> tuple[str, str]:
    s = s[s != ""]
    return (s.min(), s.max()) if len(s) else ("", "")


def build(data: Path) -> dict:
    out = data / "site" / "empresas"
    people = name_tokens(data)

    # ---------------------------------------------------------- sanctions
    src = data / "sancoes"
    day, cepim_day = _snapshot(src)
    s = sanctions(src)
    if not day:
        day = s.origem_data.max() if len(s) else ""
    s = s[s.empresa & s.doc.str.fullmatch(CNPJ)].copy()
    s["st"] = "v"
    s.loc[(s.fim != "") & (s.fim < day), "st"] = "e"          # ended, still listed
    s.loc[(s.inicio != "") & (s.inicio > day), "st"] = "f"    # starts later
    cep = _read(src / "cepim.csv")
    le = _read(src / "leniencia.csv")
    le = le[le.cnpj_do_sancionado.str.fullmatch(CNPJ)] if len(le) else pd.DataFrame(columns=["cnpj_do_sancionado"])
    ch = _read(src / "changes.csv")
    ch = ch[ch.documento.str.fullmatch(CNPJ) & (ch.tipo_de_pessoa != "F")] if len(ch) else pd.DataFrame(columns=["documento"])

    # ---------------------------------------------------------- amendments
    fav = _read(data / "emendas" / "favorecidos.csv")
    fav = fav.drop_duplicates("favorecido").set_index("favorecido") if len(fav) else pd.DataFrame(columns=["nome", "natureza_juridica"])
    nat = fav.natureza_juridica if len(fav) else pd.Series(dtype=str)
    pay = _read_dir(data / "emendas" / "pagamentos", usecols=["codigo_emenda", "ano_mes", "favorecido", "uf", "municipio", "valor"])
    if len(pay):
        pay = pay[pay.favorecido.str.fullmatch(CNPJ)]
        pay = pay[~pay.favorecido.map(nat).fillna("").str.match(PUBLIC)].assign(valor=lambda t: _money(t.valor))
    else:
        pay = pd.DataFrame(columns=["codigo_emenda", "ano_mes", "favorecido", "uf", "municipio", "valor"])
    em = _read_dir(data / "emendas" / "emendas", usecols=["codigo", "tipo", "autor_codigo", "autor"])
    em = em.drop_duplicates("codigo").set_index("codigo") if len(em) else pd.DataFrame(columns=["tipo", "autor_codigo", "autor"])
    pay["autor_codigo"] = pay.codigo_emenda.map(em.autor_codigo).fillna("") if len(em) else ""

    # ---------------------------------------------------------- contracts
    pn = data / "pncp"
    rcl = town_revenue(data)
    big = _read_dir(pn / "contratos")
    ccols = ["controle", "publicacao", "assinatura", "orgao", "esfera", "uf", "municipio_ibge", "fornecedor", "fornecedor_nome",
             "objeto", "valor_inicial", "valor_global"]
    big = big[ccols].drop_duplicates("controle", keep="last") if len(big) else pd.DataFrame(columns=ccols)
    sc = sanctioned_contracts(pn)
    cobre = sc.groupby("controle").cobre.agg(best_scope) if len(sc) else pd.Series(dtype=str)
    # Any contract signed while a bar reached (or may have reached) the buyer counts, whatever its value.
    extra = sc[sc.controle.map(cobre).isin(["sim", "possivel"]) & ~sc.controle.isin(big.controle)].drop_duplicates("controle")
    con = pd.concat([big, extra.drop(columns="cobre").assign(fornecedor_nome="")], ignore_index=True)
    con = con[con.fornecedor.str.fullmatch(CNPJ)]
    con = plausible(con, rcl)
    con["cobre"] = con.controle.map(cobre).fillna("")
    con["ano"] = con.assinatura.where(con.assinatura != "", con.publicacao).str[:4]
    dias = _read(pn / "dias.csv")

    # ---------------------------------------------------------- campaigns
    sup, pairs, cands = [], [], []
    for year, eday in ELECTIONS.items():
        f = _read(data / "tse" / year / "fornecedores.csv")
        if len(f):
            sup.append(f.assign(ano=year, dia=eday, total=_money(f.total)))
        fc = _read(data / "tse" / year / "fornecedores_candidatos.csv")
        if len(fc):
            pairs.append(fc.assign(ano=year, valor=_money(fc.valor)))
        c = _read(data / "tse" / year / "candidatos.csv")
        if len(c):
            cands.append(c[c.cargo.isin(FEDERAL)][["sq_candidato", "cargo", "uf", "nome_urna", "partido", "resultado"]].assign(ano=year))
    sup = pd.concat(sup, ignore_index=True) if sup else pd.DataFrame(columns=["cnpj", "nome", "cnae", "total", "n_candidatos", "ano", "dia"])
    sup = sup[sup.cnpj.str.fullmatch(CNPJ)]
    pairs = pd.concat(pairs, ignore_index=True) if pairs else pd.DataFrame(columns=["sq_candidato", "cnpj", "valor", "ano"])
    cands = pd.concat(cands, ignore_index=True) if cands else pd.DataFrame(columns=["sq_candidato", "cargo", "uf", "nome_urna", "partido", "resultado", "ano"])

    # ---------------------------------------------------------- red flags
    flags = {k: _read(data / "site" / "alertas" / f"{k}.csv") for k in FLAGS}

    # ---------------------------------------------------------- who is in, and their names
    keys = set(s.doc) | set(cep.get("cnpj_entidade", [])) | set(le.cnpj_do_sancionado) | set(ch.documento)
    # A contract whose value is a typo counts nowhere, and refunds can cancel a recipient's payments: neither brings
    # anyone in. Campaign suppliers come with another source.
    paid = pay.groupby("favorecido").valor.sum()
    keys |= set(con[con.suspeito != 2].fornecedor) | set(paid.index[paid > 0])
    for t in flags.values():
        if len(t) and "cnpj" in t:
            keys |= set(t.cnpj[t.cnpj.str.fullmatch(CNPJ)])
    keys = {k for k in keys if not PUBLIC.match(str(nat.get(k, "")))}
    idx = pd.DataFrame(index=pd.Index(sorted(keys), name="cnpj"))

    # A name from the most official source that has one: the Receita's (sanctions), the Portal's, the PNCP's, the TSE's.
    named = [s[["doc", "nome"]].rename(columns={"doc": "cnpj"}),
             fav.nome.rename_axis("cnpj").reset_index() if len(fav) else None,
             cep.rename(columns={"cnpj_entidade": "cnpj", "nome_entidade": "nome"})[["cnpj", "nome"]] if len(cep) else None,
             le.rename(columns={"cnpj_do_sancionado": "cnpj", "razao_social_cadastro_receita": "nome"})[["cnpj", "nome"]] if len(le) else None,
             con.sort_values("publicacao", ascending=False)[["fornecedor", "fornecedor_nome"]].rename(columns={"fornecedor": "cnpj", "fornecedor_nome": "nome"}),
             sup[["cnpj", "nome"]], ch.rename(columns={"documento": "cnpj"})[["cnpj", "nome"]] if len(ch) else None]
    names = pd.concat([t for t in named if t is not None], ignore_index=True)
    names = names[(names.nome != "") & names.cnpj.isin(keys)]
    idx["nome"] = names.drop_duplicates("cnpj").set_index("cnpj").nome.reindex(idx.index).fillna("")
    # Withheld when any of its names reads as a person's, or its legal nature is an individual's.
    person = names.assign(p=individual_firm(names.nome, people)).groupby("cnpj").p.any()
    idx["natureza"] = nat.reindex(idx.index).fillna("")
    idx["pf"] = (person.reindex(idx.index).fillna(False) | idx.natureza.isin(PERSONAL)).astype(int)
    hidden = set(idx.index[idx.pf == 1])
    full_name = idx.nome.copy()
    idx.loc[idx.pf == 1, "nome"] = ""
    cnae = sup.sort_values("ano").drop_duplicates("cnpj", keep="last").set_index("cnpj").cnae
    idx["cnae"] = cnae.reindex(idx.index).fillna("")

    profile: dict[str, dict] = {k: {} for k in idx.index}

    def put(key: str, groups: dict) -> None:
        for doc, v in groups.items():
            if doc in profile:
                profile[doc][key] = v

    # ---------------------------------------------------------- per company: sanctions
    # Categories and scopes are long, repeated texts: profiles carry their position in resumo.json's lists.
    categorias, abrangencias = sorted(set(s.categoria)), sorted(set(s.abrangencia))
    scols = ["lista", "codigo", "cat", "inicio", "fim", "orgao", "esf", "uf", "abr", "multa", "st"]
    ss = s.assign(multa=s.multa.round(2), cat=s.categoria.map({v: i for i, v in enumerate(categorias)}),
                  abr=s.abrangencia.map({v: i for i, v in enumerate(abrangencias)}), esf=s.esfera.str[:1])
    ss = ss.sort_values(["doc", "inicio", "lista", "codigo"])
    put("s", lists(ss, "doc", scols))
    if len(ch):
        put("h", lists(ch.sort_values(["documento", "data", "lista", "codigo"]), "documento", ["data", "lista", "codigo", "mudanca"]))
    if len(cep):
        put("p", lists(cep.sort_values(["cnpj_entidade", "numero_convenio"]), "cnpj_entidade", ["numero_convenio", "orgao_concedente", "motivo_do_impedimento"]))
    if len(le):
        put("l", lists(le.sort_values(["cnpj_do_sancionado", "data_de_inicio_do_acordo", "id_do_acordo"]).drop_duplicates(["cnpj_do_sancionado", "id_do_acordo"]),
                       "cnpj_do_sancionado", ["id_do_acordo", "data_de_inicio_do_acordo", "data_de_fim_do_acordo", "situacao_do_acordo_de_lenienica", "orgao_sancionador"]))
    idx["sancoes"] = s.groupby("doc").size().reindex(idx.index).fillna(0).astype(int)
    idx["vigentes"] = s[s.st == "v"].groupby("doc").size().reindex(idx.index).fillna(0).astype(int)
    barring_now = s[(s.st == "v") & s.bars]
    idx["impedida"] = idx.index.isin(set(barring_now.doc)).astype(int)
    idx["cepim"] = cep.groupby("cnpj_entidade").size().reindex(idx.index).fillna(0).astype(int) if len(cep) else 0
    idx["leniencia"] = le.groupby("cnpj_do_sancionado").id_do_acordo.nunique().reindex(idx.index).fillna(0).astype(int) if len(le) else 0
    idx["saidas"] = (ch[ch.mudanca == "saiu"].groupby("documento").size().reindex(idx.index).fillna(0).astype(int)) if len(ch) else 0

    # ---------------------------------------------------------- per company: contracts
    cx = con[con.fornecedor.isin(keys)].copy()
    gone = cx[cx.suspeito == 2]
    cx = cx[cx.suspeito != 2]
    hid = cx.fornecedor.isin(hidden)
    cx.loc[hid, "objeto"] = scrub(cx.objeto[hid], cx.fornecedor[hid].map(full_name).fillna(""))
    cx["objeto"] = short_object(cx.objeto)
    cx["v"] = cx.v.round(2)
    cx["barred"] = cx.cobre.isin(["sim", "possivel"])
    cg = cx.groupby("fornecedor")
    idx["contratos"] = cg.size().reindex(idx.index).fillna(0).astype(int)
    idx["contratos_valor"] = cg.v.sum().reindex(idx.index).fillna(0.0).round(2)
    idx["contratos_impedida"] = cx[cx.barred].groupby("fornecedor").size().reindex(idx.index).fillna(0).astype(int)
    by_year = cx.groupby(["fornecedor", "ano"]).agg(n=("v", "size"), v=("v", "sum")).reset_index()
    by_year["v"] = by_year.v.round(2)
    years = lists(by_year, "fornecedor", ["ano", "n", "v"])
    buyers = cx.groupby(["fornecedor", "orgao", "uf"]).agg(n=("v", "size"), v=("v", "sum")).reset_index()
    buyers = buyers.sort_values(["fornecedor", "v", "orgao"], ascending=[True, False, True])
    buyers["v"] = buyers.v.round(2)
    n_buyers = buyers.groupby("fornecedor").orgao.nunique()
    top_b = lists(buyers[buyers.groupby("fornecedor").cumcount() < TOP_BUYERS], "fornecedor", ["orgao", "uf", "n", "v"])
    # The largest contracts, and every one signed while barred (they are why a reader looks).
    cx = cx.sort_values(["fornecedor", "v", "controle"], ascending=[True, False, True])
    shown = (cx.groupby("fornecedor").cumcount() < TOP_CONTRACTS) | (cx.barred & (cx.groupby(["fornecedor", "barred"]).cumcount() < TOP_BARRED))
    tcols = ["assinatura", "orgao", "uf", "objeto", "v", "cobre", "controle"]
    top_c = lists(cx[shown], "fornecedor", tcols + ["suspeito"])
    top_c = {d: [r[:-1] + ([1] if r[-1] else []) for r in rows] for d, rows in top_c.items()}   # "fixed" only when it was
    tot = cg.v.sum().round(2)
    bn = cx[cx.barred].groupby("fornecedor").v.agg(["size", "sum"])
    for d in tot.index:
        c = {"n": int(idx.at[d, "contratos"]), "v": float(tot[d]), "t": top_c.get(d, [])}
        if c["n"] > len(c["t"]):   # otherwise the list itself shows every year and buyer
            c.update(y=years.get(d, []), o=top_b.get(d, []), no=int(n_buyers.get(d, 0)))
        if d in bn.index:
            c["b"] = [int(bn.at[d, "size"]), round(float(bn.at[d, "sum"]), 2)]
        profile[d]["c"] = c
    for d, k in gone.groupby("fornecedor").size().items():
        if d in profile:
            profile[d].setdefault("c", {"n": 0, "v": 0.0, "t": []})["x"] = int(k)

    # ---------------------------------------------------------- per company: amendments
    px = pay[pay.favorecido.isin(keys)].copy()
    px["ano"] = px.ano_mes.str[:4]
    px["barrado"] = while_barred(px.rename(columns={"favorecido": "doc"}), s, "doc", "ano_mes", federal_scope, month=True)
    px["vb"] = px.valor.where(px.barrado != "", 0.0)
    pg = px.groupby("favorecido")
    idx["emendas"] = pg.valor.sum().reindex(idx.index).fillna(0.0).round(2)
    idx["emendas_impedida"] = pg.vb.sum().reindex(idx.index).fillna(0.0).round(2)
    ey = px.groupby(["favorecido", "ano"])[["valor", "vb"]].sum().round(2).reset_index()
    ey_d = {d: [r if r[2] else r[:2] for r in rows] for d, rows in lists(ey, "favorecido", ["ano", "valor", "vb"]).items()}   # while barred, when any
    au = px[px.autor_codigo != ""].groupby(["favorecido", "autor_codigo"]).agg(v=("valor", "sum"), n=("valor", "size"), vb=("vb", "sum")).reset_index()
    au = au.sort_values(["favorecido", "v", "autor_codigo"], ascending=[True, False, True])
    au[["v", "vb"]] = au[["v", "vb"]].round(2)
    rank = au.groupby("favorecido").cumcount()
    au_d = {d: [r if r[2] else r[:2] for r in rows] for d, rows in lists(au[rank < TOP_AUTHORS], "favorecido", ["autor_codigo", "v", "vb"]).items()}
    rest = au[rank >= TOP_AUTHORS].groupby("favorecido").v.agg(["size", "sum"])
    noauthor = px[px.autor_codigo == ""].groupby("favorecido").valor.sum().round(2)
    place = (px[px.uf != ""].groupby(["favorecido", "municipio", "uf"]).valor.sum().reset_index()
             .sort_values(["favorecido", "valor", "municipio"], ascending=[True, False, True]).drop_duplicates("favorecido").set_index("favorecido"))
    idx["local"] = (place.municipio + "/" + place.uf).reindex(idx.index).fillna("")
    for d in pg.size().index:
        e = {"v": float(idx.at[d, "emendas"]), "y": ey_d.get(d, [])}
        if noauthor.get(d, 0.0):
            e["u"] = float(noauthor[d])
        if d in au_d:
            e["a"] = au_d[d]
        if d in rest.index:
            e["r"] = [int(rest.at[d, "size"]), round(float(rest.at[d, "sum"]), 2)]
        profile[d]["e"] = e
    used_authors = set(au.autor_codigo)

    # ---------------------------------------------------------- per company: campaigns
    sx = sup[sup.cnpj.isin(keys)].copy()
    sx["barrado"] = while_barred(sx.rename(columns={"cnpj": "doc"}), s, "doc", "dia") != ""
    px2 = pairs[pairs.cnpj.isin(keys)].merge(cands, on=["sq_candidato", "ano"], how="left").fillna("")
    x = _read(data / "ref" / "politicians.csv")
    # A candidate who became a deputy links to their profile on this site.
    deps = deputies(data)
    if len(x) and len(deps):
        pes = x[x.fonte == "tse"].drop_duplicates("id").set_index("id").pessoa
        in_leg = {leg: set(t.pessoa) for leg, t in deps.groupby("leg")}
        cam = deps.drop_duplicates("pessoa").set_index("pessoa").deputado_id
        who = px2.sq_candidato.map(pes).fillna("")
        # The legislature the election chose, else the other one this site covers.
        first = px2.ano.map({"2018": 56, "2022": 57}).fillna(57).astype(int)
        leg = [f if p_ in in_leg.get(f, ()) else (o if p_ in in_leg.get(o, ()) else 0) for p_, f, o in zip(who, first, 113 - first)]
        px2["link"] = member_link(who.map(cam).fillna(""), pd.Series(leg, index=px2.index), pd.Series("", index=px2.index))
    else:
        px2["link"] = ""
    px2["cargo"] = px2.cargo.map(FEDERAL).fillna("")
    px2["resultado"] = px2.resultado.map(RESULT).fillna("")
    px2["nome_urna"] = px2.nome_urna.map(display)
    px2 = px2.sort_values(["cnpj", "ano", "valor", "sq_candidato"], ascending=[True, True, False, True])
    px2["valor"] = px2.valor.round(2)
    tse_years = sorted(set(sx.ano) | set(px2.ano))
    allc = {(c_, y): (round(float(t_), 2), int(n_), 1 if b_ else 0) for c_, y, t_, n_, b_ in sx[["cnpj", "ano", "total", "n_candidatos", "barrado"]].itertuples(index=False, name=None)}
    px2["k"] = list(zip(px2.cnpj, px2.ano))
    rank = px2.groupby("k").cumcount()
    who_c = lists(px2[rank < TOP_CANDIDATES], "k", ["nome_urna", "partido", "uf", "cargo", "resultado", "link", "valor"])
    pair_n = px2.groupby("k").valor.agg(["size", "sum"])
    rest_c = px2[rank >= TOP_CANDIDATES].groupby("k").valor.agg(["size", "sum"])
    idx["campanhas"] = (sx.groupby("cnpj").total.sum().reindex(idx.index).fillna(0.0)).round(2)
    fed = px2.groupby("cnpj").valor.sum()
    idx["campanhas"] = idx.campanhas.where(idx.campanhas > 0, fed.reindex(idx.index).fillna(0.0).round(2))
    for d in sorted(set(sx.cnpj) | set(px2.cnpj)):
        rows = []
        for y in tse_years:
            a, k = allc.get((d, y)), (d, y)
            if a is None and k not in who_c:
                continue
            row = [y, *(a if a else (None, None, 0))]
            if k in who_c:
                row += [who_c[k], int(rest_c.at[k, "size"]) if k in rest_c.index else 0, round(float(rest_c.at[k, "sum"]), 2) if k in rest_c.index else 0.0,
                        int(pair_n.at[k, "size"]), round(float(pair_n.at[k, "sum"]), 2)]
            rows.append(row)
        profile[d]["t"] = rows

    # ---------------------------------------------------------- per company: red flags
    idx["alertas"] = 0
    for k, t in flags.items():
        if not len(t) or "cnpj" not in t:
            continue
        t = t[t.cnpj.isin(keys)]
        for c in ("valor", "emendas", "campanha", "share", "maior_share", "contratos"):
            if c in t:
                t = t.assign(**{c: _money(t[c])})
        if "deputado_id" in t:
            t = t.assign(link=member_link(t.deputado_id, t.leg, t.senador_id))
        if "autor" in t:
            t = t.assign(autor=t.autor.map(display))
        for d, g in t.groupby("cnpj"):
            if k == "emendas_impedidas":
                det = g.sort_values("valor", ascending=False)[["autor", "partido", "uf", "link", "barrado", "valor"]].head(10).values.tolist()
                v = g.valor.sum()
            elif k in ("contratos_impedidas", "leniencia_contratos"):
                det, v = [], g.valor.sum()
            elif k == "campanha_emendas":
                det = g.sort_values("emendas", ascending=False)[["deputado", "partido", "uf", "link", "eleicao", "campanha", "emendas"]].values.tolist()
                v = g.emendas.sum()
            elif k == "concentracao":
                det = g.sort_values("share", ascending=False)[["deputado", "partido", "uf", "link", "share", "valor"]].values.tolist()
                v = g.valor.sum()
            else:   # fornecedor_dominante: one row per buyer
                det = g.sort_values("valor", ascending=False)[["orgao", "uf", "contratos", "maior_share"]].head(10).values.tolist()
                v = None
            profile[d].setdefault("f", {})[k] = [len(g), None if v is None else round(float(v), 2), det]
        idx.loc[idx.index.isin(set(t.cnpj)), "alertas"] += 1

    # ---------------------------------------------------------- write
    idx["fontes"] = ((idx.sancoes + idx.cepim + idx.leniencia > 0).map({True: "S", False: ""})
                     + ((idx.sancoes + idx.cepim + idx.leniencia == 0) & (idx.saidas > 0)).map({True: "H", False: ""})
                     + (idx.contratos > 0).map({True: "C", False: ""}) + (idx.emendas > 0).map({True: "E", False: ""})
                     + (idx.campanhas > 0).map({True: "T", False: ""}) + (idx.alertas > 0).map({True: "A", False: ""}))
    # Legal natures and activities repeat: profiles carry their position in resumo.json's lists.
    naturezas, cnaes = sorted(set(idx.natureza) - {""}), sorted(set(idx.cnae) - {""})
    nj, cn = {v: i for i, v in enumerate(naturezas)}, {v: i for i, v in enumerate(cnaes)}
    for d, nome, pf, natureza, ativ, local in idx[["nome", "pf", "natureza", "cnae", "local"]].itertuples(name=None):
        p = profile[d]
        p["n"] = nome
        if pf:
            p["pf"] = 1
        for k, v in (("nj", nj.get(natureza)), ("cn", cn.get(ativ)), ("lc", local or None)):
            if v is not None:   # a position can be 0
                p[k] = v
    shard_dir = out / "perfis"
    shard_dir.mkdir(parents=True, exist_ok=True)
    shards: dict[str, dict] = {}
    for d in idx.index:
        shards.setdefault(d[:SHARD], {})[d] = profile[d]
    keep = set()
    for k, v in shards.items():
        p = shard_dir / f"{k}.json"
        write_json(whole(v), p, digits=4)
        keep.add(p.name)
    for p in shard_dir.glob("*.json"):
        if p.name not in keep:
            p.unlink()

    # The search index: what a suggestion shows, and what orders them (public money received).
    ix = idx.reset_index()
    ix["valor"] = ((ix.emendas + ix.contratos_valor) / 1000).round(0).astype("int64")   # R$ thousand: only orders suggestions
    csv(ix[["cnpj", "nome", "pf", "fontes", "valor"]], out / "indice.csv")
    ix["n_fontes"] = ix.fontes.str.replace("H", "").str.len()
    feat = ix[(ix.n_fontes >= 2) | (ix.alertas > 0)].sort_values(["alertas", "n_fontes", "valor", "cnpj"], ascending=[False, False, False, True]).head(FEATURED)
    csv(feat[["cnpj", "nome", "pf", "fontes", "natureza", "vigentes", "impedida", "contratos", "contratos_valor", "contratos_impedida", "emendas",
              "emendas_impedida", "campanhas", "alertas"]], out / "destaques.csv")

    # Amendment authors the profiles name: members of Congress by name, party and state; benches, committees, rapporteurs.
    if len(em):
        a = em[em.autor_codigo.isin(used_authors)].drop_duplicates("autor_codigo")[["autor_codigo", "autor", "tipo"]]
        who = x[x.fonte == "emendas"].drop_duplicates("id").set_index("id").pessoa if len(x) else pd.Series(dtype=str)
        a["pessoa"] = a.autor_codigo.map(who).fillna("")
        m = members(data, deps)
        for c in ("nome", "partido", "uf", "deputado_id", "senador_id"):
            a[c] = a.pessoa.map(m[c]).fillna("") if len(m) else ""
        a["leg"] = a.pessoa.map(m.leg).fillna(0).astype(int) if len(m) else 0
        a["link"] = member_link(a.deputado_id, a.leg.astype(str), a.senador_id)
        a["nome"] = a.nome.where(a.nome != "", a.autor.map(display))
        a["tipo"] = a.tipo.where(~a.tipo.isin(["individual", "especial"]) | (a.pessoa == ""), "parlamentar")
        csv(a[["autor_codigo", "nome", "tipo", "partido", "uf", "link"]].sort_values("autor_codigo"), out / "autores.csv")
    else:
        csv(pd.DataFrame(columns=["autor_codigo", "nome", "tipo", "partido", "uf", "link"]), out / "autores.csv")

    first, last = (dias.dia.min(), dias.dia.max()) if len(dias) else ("", "")
    span = (pd.Timestamp(last) - pd.Timestamp(START)).days + 1 if last else 0
    resumo = {
        "empresas": len(idx), "nomes_omitidos": len(hidden), "shards": len(shards),
        "por_fonte": {"sancoes": int((idx.sancoes + idx.cepim + idx.leniencia > 0).sum()), "saidas": int((idx.saidas > 0).sum()),
                      "contratos": int((idx.contratos > 0).sum()), "emendas": int((idx.emendas > 0).sum()),
                      "campanhas": int((idx.campanhas > 0).sum()), "alertas": int((idx.alertas > 0).sum())},
        "em_varias": int((ix.n_fontes >= 2).sum()),
        "sancoes": {"snapshot": day, "cepim_snapshot": cepim_day, "historico_desde": ch.data.min() if len(ch) else "",
                    "vigentes": int((idx.vigentes > 0).sum()), "impedidas": int(idx.impedida.sum())},
        "pncp": {"days_read": len(dias), "first": first, "last": last, "since": START, "span_days": span,
                 "contratos": int(idx.contratos.sum()), "valor": float(idx.contratos_valor.sum()), "descartados": int(len(gone))},
        "emendas": {"first": _ym_range(pay.ano_mes)[0], "last": _ym_range(pay.ano_mes)[1], "valor": float(idx.emendas.sum())},
        "tse": {"eleicoes": tse_years},
        "alertas": {k: int((idx.index.isin(set(t.cnpj)) if len(t) and "cnpj" in t else pd.Series(False)).sum()) for k, t in flags.items()},
        "naturezas": naturezas, "cnaes": cnaes, "categorias": categorias, "abrangencias": abrangencias,
        "caps": {"contracts": TOP_CONTRACTS, "buyers": TOP_BUYERS, "authors": TOP_AUTHORS, "candidates": TOP_CANDIDATES, "object": OBJ},
    }
    write_json(resumo, out / "resumo.json", digits=2)
    return {"companies": len(idx), "withheld": len(hidden), "shards": len(shards), "featured": len(feat)}
