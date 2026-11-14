"""Summaries for the town profile page ("Meu município"): ``data/site/municipios/``.

    index.csv            every municipality: IBGE code, name, state, population (for the search box)
    resumo.json          what each source covers, amendment money to town governments by year, and the
                         medians of similar towns (same state; same population band), year by year
    perfil/<NNNN>.json   the profiles of the towns whose IBGE code starts with NNNN, about a dozen a file:

        n, uf, p, k, cap   name, state, population, population band, state capital (1)
        m                  mayors elected: [election year, election date, name, party, supplementary (1)]
        a                  amendments paid to the town government (its own CNPJ, its funds and other municipal
                           bodies, matched by recipient):
            y              per payment year: [year, total, then by type in TIPOS order, of the total what went to
                           its funds and other bodies rather than its own CNPJ, paid to private bodies based in
                           the town, from authors of the mayor's party, from authors whose party and mayor are
                           known]
            au             the authors who sent the most, then the rest summed: [kind, name, party, house,
                           total, Pix, first year, last year, extra]. kind p: a member of Congress (extra: their
                           deputy profile, "leg:id"); u: an author code not linked to a person; c: a bench,
                           committee or the rapporteur (extra: the amendment type); n: payments without an
                           amendment code; o: every other author (extra: how many)
            pa             by the author's party, under today's name: [party, total]
            mp             since 2017: [share from the mayor's party, the same share by the state's mix, money
                           whose author's party and mayor are known]
        c                  PNCP contracts of the town's bodies (municipal sphere), values through pncp.plausible():
            n, v, x        large contracts (R$ 1 million or more), their value; contracts left out as typos
            f              largest suppliers: [CNPJ, name ("" when withheld), contracts, value, reach]; reach is
                           the widest of the sanctions under which the supplier signed with the town's bodies
            t              largest contracts: [signed, body, supplier, object, value]
            s              contracts of any value signed with a supplier barred that day, by whether the
                           sanction reached the buyer: {sim|possivel|nao: [contracts, value]}
            sl             those where it did or may have: [signed, body, CNPJ, supplier, object, value, reach,
                           sanction, sanctioning body]
        f                  Siconfi: y [year, payroll % of revenue, status, revenue (RCL), payroll, free cash];
                           nf years consulted for which the town filed no report
        r                  rank among similar towns: {metric: [year, value, percentile in the state, percentile in
                           the population band]}

Names of suppliers that are people (private individuals, individual firms) are withheld. Rules and
sources: methodology/municipios.md.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..ref.prefeitos import mayor_by_year
from .alertas import INDIVIDUAL, PRIVATE, display
from .common import csv, write_json
from .deputados import party_in
from .emendas import _people, town_codes
from .pncp import START, contracts, plausible, read_sanctioned, town_revenue
from .sancoes import individual_firm, name_tokens
from .siconfi import SIZES, size_class

TIPOS = ["especial", "individual", "bancada", "comissao", "relator", ""]   # "" is a payment without an amendment code
TOP_AUTHORS = 12
TOP_SUPPLIERS = 8
TOP_CONTRACTS = 5
TOP_BARRED = 25
OBJ = 120
MAYORS_FROM = 2017   # the first term in data/ref/prefeitos.csv (2016 election)
REACH = {"nao": 1, "possivel": 2, "sim": 3}
NO_PARTY = {"", "S.PART.", "S/PARTIDO", "SEM PARTIDO"}
FISCAL = ["ano", "dtp_pct", "situacao", "rcl", "dtp", "liquida_livre"]


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def reais(x):
    """Money in whole reais for the profiles: the page shows R$ mil and R$ mi, never centavos."""
    if isinstance(x, pd.Series):
        return x.round().astype("Int64")
    return None if x is None or pd.isna(x) else int(round(x))


def _years(folder: Path, cols: list[str]) -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted(folder.glob("*.csv"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


def today(label: str) -> str:
    """A party under today's name, every renaming and merger applied (PRP -> PATRIOTA -> PRD)."""
    return "" if label.upper() in NO_PARTY else party_in(party_in(label, 9999), 9999)


def party_then(labels: pd.Series, years: pd.Series) -> pd.Series:
    """Each party as it stood in that year (``deputados.party_in``), once per distinct pair."""
    pairs = {(p, y): ("" if p.upper() in NO_PARTY else party_in(p, y)) for p, y in set(zip(labels, years))}
    return pd.Series([pairs[(p, y)] for p, y in zip(labels, years)], index=labels.index, dtype=str)


def percentile(v: pd.Series, keys: list[pd.Series]) -> pd.Series:
    """Share of each group below the value, ties counted half; blanks stay blank and are not counted."""
    g = v.groupby(keys)
    return (g.rank(method="average") - 0.5) / g.transform("count")


def towns(data: Path) -> pd.DataFrame:
    e = _read(data / "siconfi" / "entes.csv")
    e["habitantes"] = _num(e.populacao)
    e["faixa"] = size_class(e.habitantes.fillna(0))
    return e.sort_values("cod_ibge").reset_index(drop=True)


def is_personal(cnpj: pd.Series, nome: pd.Series, tipo: pd.Series, natureza: pd.Series, people: set[str]) -> pd.Series:
    """A supplier whose name is a person's: a private individual (masked CPF), an individual firm by legal nature,
    or a name made of people's names and initials (``sancoes.individual_firm``: ``"P R C DUARTE"``)."""
    from ..ref.politicians import norm
    # A corporation ("BAYER S.A.") is not a person's firm, though "S" and "A" are also initials in people's names.
    # Only "S A" as written apart: a bare "SA" may be the surname Sá.
    corporation = nome.fillna("").map(lambda n: norm(n).endswith(" S A"))
    return (tipo == "PF") | cnpj.str.contains(r"\*", regex=True) | natureza.isin(INDIVIDUAL) | (individual_firm(nome, people) & ~corporation)


# ------------------------------------------------------------ amendments


def party_months(data: Path) -> pd.DataFrame:
    """Each linked politician's party label, month by month, from the Câmara's and the Senado's monthly tables."""
    x = _read(data / "ref" / "politicians.csv")
    parts = []
    for fonte, folder, key in (("camara", data / "camara" / "deputies", "deputado_id"), ("senado", data / "senado" / "senators", "senador_id")):
        ids = x[x.fonte == fonte].set_index("id").pessoa if len(x) else pd.Series(dtype=str)
        for f in sorted(folder.glob("*.csv")):
            t = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=[key, "partido"])
            t = t[~t.partido.str.upper().isin(NO_PARTY)]
            parts.append(pd.DataFrame({"pessoa": t[key].map(ids), "ym": f.stem, "partido": t.partido}).dropna(subset=["pessoa"]))
    if not parts:
        return pd.DataFrame(columns=["pessoa", "ym", "partido"])
    return pd.concat(parts, ignore_index=True).drop_duplicates(["pessoa", "ym"], keep="last")


def party_at(pay: pd.DataFrame, months: pd.DataFrame) -> pd.Series:
    """The author's party label in the month of each payment: that month's or the latest before it, else the first
    after it (payments go on after a member leaves office, and a member's first months may be missing)."""
    out = pd.Series("", index=pay.index, dtype=object)
    p = pay[pay.pessoa != ""]
    if p.empty or months.empty:
        return out

    def t(ym: pd.Series):
        return (ym.str[:4].astype(int) * 12 + ym.str[5:7].astype(int)).values
    left = pd.DataFrame({"i": p.index, "pessoa": p.pessoa.values, "t": t(p.ano_mes)}).sort_values("t")
    right = pd.DataFrame({"pessoa": months.pessoa.values, "t": t(months.ym), "partido": months.partido.values}).sort_values("t")
    for direction in ("backward", "forward"):
        m = pd.merge_asof(left, right, on="t", by="pessoa", direction=direction).set_index("i").partido.dropna()
        m = m[out.loc[m.index] == ""]
        out.loc[m.index] = m
    return out


def town_amendments(data: Path, e: pd.DataFrame) -> pd.DataFrame:
    """Amendment payments to each town's government, and to private bodies based there.

    ``alvo``: ``prefeitura`` (the municipality's own CNPJ, where "Pix" transfers land), ``municipal`` (its funds,
    autarchies and other municipal bodies, by legal nature and the recipient's town) or ``privado`` (associations,
    foundations and companies based in the town). State and federal bodies, state companies and the banks that
    carry transfers are left out: they sit in one town but spend for a wider area.
    """
    cols = ["codigo_emenda", "ano_mes", "favorecido", "uf", "municipio", "valor"]
    files = sorted((data / "emendas" / "pagamentos").glob("*.csv"))
    pg = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=cols) for f in files], ignore_index=True) if files else pd.DataFrame(columns=cols)
    keep = ["cod_ibge", "ano", "ano_mes", "alvo", "tipo", "chave", "autor", "pessoa", "valor"]
    if pg.empty:
        return pd.DataFrame(columns=keep)
    own = pg.favorecido.map(dict(zip(e.cnpj, e.cod_ibge))).fillna("")
    place = pd.Series(town_codes(data, pg), index=pg.index)
    fav = _read(data / "emendas" / "favorecidos.csv")
    nat = pg.favorecido.map(fav.drop_duplicates("favorecido").set_index("favorecido").natureza_juridica).fillna("") if len(fav) else pd.Series("", index=pg.index)
    municipal = (nat == "Município") | nat.str.endswith("Municipal")
    alvo = np.select([own != "", (place != "") & municipal, (place != "") & nat.isin(PRIVATE)], ["prefeitura", "municipal", "privado"], "")
    pg = pg.assign(cod_ibge=own.where(own != "", place), alvo=alvo)
    pg = pg[pg.alvo != ""].copy()
    pg["valor"] = _num(pg.valor).fillna(0.0)
    pg["ano"] = pg.ano_mes.str[:4].astype(int)

    em = _years(data / "emendas" / "emendas", ["codigo", "tipo", "autor_codigo", "autor"])
    em = em[em.codigo != ""].drop_duplicates("codigo").set_index("codigo")
    for c in ("tipo", "autor_codigo", "autor"):
        pg[c] = pg.codigo_emenda.map(em[c]).fillna("")
    x = _read(data / "ref" / "politicians.csv")
    person = x[x.fonte == "emendas"].set_index("id").pessoa if len(x) else pd.Series(dtype=str)
    own_amendment = pg.tipo.isin(["individual", "especial"])
    pg["pessoa"] = pg.autor_codigo.map(person).where(own_amendment).fillna("")
    # One key per author: the person; an author code not linked to one; a bench, committee or the rapporteur; no code.
    pg["chave"] = np.select([pg.pessoa != "", own_amendment & (pg.autor_codigo != ""), pg.tipo != ""],
                            [pg.pessoa, "autor:" + pg.autor_codigo, "col:" + pg.tipo + ":" + pg.autor], "sem")
    return pg[keep]


def first_rows(t: pd.DataFrame, by: str, n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a frame already in order into each group's first ``n`` rows and the rest."""
    k = t.groupby(by, sort=False).cumcount()
    return t[k < n], t[k >= n]


def ranked(t: pd.DataFrame, by: str, value: str, tie: str) -> pd.DataFrame:
    """Rows by group, largest value first (to the centavo), ties by ``tie``: the same order on every run."""
    return t.assign(_r=-t[value].round(2)).sort_values([by, "_r", tie]).drop(columns="_r")


def author_rows(gov: pd.DataFrame, who: pd.DataFrame, links: dict) -> dict[str, list]:
    """Per town, its authors largest first: the top TOP_AUTHORS, then everyone else summed."""
    a = gov.groupby(["cod_ibge", "chave"]).agg(total=("valor", "sum"), pix=("pix", "sum"), y0=("ano", "min"), y1=("ano", "max"),
                                               autor=("autor", "last"), tipo=("tipo", "last"), partido=("partido_hoje", "last")).reset_index()
    a = ranked(a[a.total.round(2) != 0], "cod_ibge", "total", "chave")
    top, rest = first_rows(a, "cod_ibge", TOP_AUTHORS)
    name, house = (who.nome.to_dict(), who.casa.to_dict()) if len(who) else ({}, {})
    out: dict[str, list] = {}
    for r in top.itertuples():
        k, span = r.chave, [reais(r.total), reais(r.pix), int(r.y0), int(r.y1)]
        if k == "sem":
            row = ["n", "", "", "", *span, ""]
        elif k.startswith("col:"):
            row = ["c", display(r.autor), "", "", *span, r.tipo]
        elif k.startswith("autor:"):
            row = ["u", display(r.autor), r.partido, "", *span, ""]
        else:
            row = ["p", display(name.get(k) or r.autor), r.partido, house.get(k, ""), *span, links.get(k, "")]
        out.setdefault(r.cod_ibge, []).append(row)
    for cod, g in rest.groupby("cod_ibge"):
        out[cod].append(["o", "", "", "", reais(g.total.sum()), reais(g.pix.sum()), int(g.y0.min()), int(g.y1.max()), len(g)])
    return out


# ------------------------------------------------------------ build


def build(data: Path) -> dict:
    out = data / "site" / "municipios"
    e = towns(data)
    codes = e.cod_ibge.tolist()
    ix = e.set_index("cod_ibge")
    pop, uf_of, band_of = ix.habitantes, ix.uf, ix.faixa

    # ---------------------------------------------------------- amendments and mayors
    pay = town_amendments(data, e)
    last_year = int(pay.ano.max()) if len(pay) else pd.Timestamp.now().year
    pre = _read(data / "ref" / "prefeitos.csv")
    mb = mayor_by_year(pre, range(MAYORS_FROM, last_year + 1)) if len(pre) else pd.DataFrame(columns=["exercicio", "cod_ibge", "partido"])
    mayor = mb.set_index(["cod_ibge", "exercicio"]).partido

    gov = pay[pay.alvo != "privado"].copy()
    gov["partido"] = party_at(gov, party_months(data))
    gov["partido_ano"] = party_then(gov.partido, gov.ano)
    gov["partido_hoje"] = gov.partido.map({p: today(p) for p in gov.partido.unique()})
    gov["prefeito"] = party_then(pd.Series(mayor.reindex(pd.MultiIndex.from_arrays([gov.cod_ibge, gov.ano])).fillna("").values, index=gov.index), gov.ano)
    gov["conhecido"] = gov.valor.where((gov.partido_ano != "") & (gov.prefeito != ""), 0.0)
    gov["mesmo"] = gov.conhecido.where(gov.partido_ano == gov.prefeito, 0.0)
    gov["pix"] = gov.valor.where(gov.tipo == "especial", 0.0)
    gov["uf"] = gov.cod_ibge.map(uf_of)
    # The state's mix: of the money its town governments got from authors of known party that year, each party's share.
    known = gov[gov.partido_ano != ""]
    mix = (known.groupby(["ano", "uf", "partido_ano"]).valor.sum() / known.groupby(["ano", "uf"]).valor.sum()).to_dict()
    gov["base"] = gov.conhecido * np.array([mix.get(k, 0.0) for k in zip(gov.ano, gov.uf, gov.prefeito)], dtype=float)

    yr = gov.pivot_table(index=["cod_ibge", "ano"], columns="tipo", values="valor", aggfunc="sum", fill_value=0.0).reindex(columns=TIPOS, fill_value=0.0)
    yr["total"] = yr.sum(axis=1)
    yr = yr.join(gov.groupby(["cod_ibge", "ano"])[["mesmo", "conhecido", "base"]].sum())
    yr = yr.join(gov[gov.alvo == "municipal"].groupby(["cod_ibge", "ano"]).valor.sum().rename("municipal"))
    yr = yr.join(pay[pay.alvo == "privado"].groupby(["cod_ibge", "ano"]).valor.sum().rename("privado"), how="outer").fillna(0.0)

    who = _people(data).drop_duplicates("pessoa").set_index("pessoa") if (data / "ref" / "politicians.csv").exists() else pd.DataFrame()
    links = {}
    for leg in (56, 57):   # the newest legislature wins
        v = _read(data / "views" / f"deputados_{leg}.csv")
        if len(v):
            links.update({p: f"{leg}:{d}" for p, d in zip(v.pessoa, v.deputado_id)})

    years = list(range(int(pay.ano.min()), last_year + 1)) if len(pay) else []
    grid = pd.MultiIndex.from_product([codes, years])
    town_of = grid.get_level_values(0)
    em_hab = pd.DataFrame({"v": yr.total.reindex(grid).fillna(0.0).values / pop.reindex(town_of).values, "ano": grid.get_level_values(1),
                           "uf": uf_of.reindex(town_of).values, "faixa": band_of.reindex(town_of).values}, index=grid)

    # ---------------------------------------------------------- contracts
    src = data / "pncp"
    rcl = town_revenue(data)
    c = contracts(src, rcl)
    cm = c[(c.esfera == "M") & c.municipio_ibge.isin(codes)]
    left_out = cm[cm.suspeito == 2].groupby("municipio_ibge").size()
    cm = cm[cm.suspeito != 2]
    sc = read_sanctioned(src)   # every contract signed with a company barred that day, any value
    sc = sc[(sc.esfera == "M") & sc.municipio_ibge.isin(codes) & sc.cobre.isin(REACH)]
    sc = plausible(sc, rcl)
    sc = sc[sc.suspeito != 2].assign(r=lambda t: t.cobre.map(REACH))
    sc = sc.sort_values(["controle", "r", "lista", "codigo_sancao"]).drop_duplicates("controle", keep="last")   # the widest reach per contract

    people = name_tokens(data)
    fav = _read(data / "emendas" / "favorecidos.csv")
    natureza = fav.drop_duplicates("favorecido").set_index("favorecido").natureza_juridica if len(fav) else pd.Series(dtype=str)

    def shown(t: pd.DataFrame) -> pd.Series:
        hide = is_personal(t.fornecedor, t.fornecedor_nome, t.fornecedor_tipo, t.fornecedor.map(natureza).fillna(""), people)
        return t.fornecedor_nome.where(~hide, "")

    cm = cm.assign(nome=shown(cm))
    sc = sc.assign(nome=shown(sc))
    c_val = cm.groupby("municipio_ibge").v.sum().reindex(codes).fillna(0.0)
    c_hab = pd.DataFrame({"v": c_val.values / pop.reindex(codes).values, "uf": uf_of.reindex(codes).values, "faixa": band_of.reindex(codes).values}, index=codes)
    reach = sc.groupby(["municipio_ibge", "fornecedor"]).r.max().to_dict()

    # ---------------------------------------------------------- Siconfi
    sic = data / "siconfi"
    pes = _years(sic / "pessoal", ["cod_ibge", "ano", "periodicidade", "periodo", "rcl", "rcl_ajustada", "dtp", "dtp_pct", "situacao"])
    pes = pes.sort_values(["cod_ibge", "ano", "periodicidade", "periodo"]).drop_duplicates(["cod_ibge", "ano"], keep="last")
    pes = pes.assign(ano=pes.ano.astype(int), dtp_pct=_num(pes.dtp_pct), rcl=_num(pes.rcl_ajustada).fillna(_num(pes.rcl)), dtp=_num(pes.dtp))
    pes["situacao"] = pes.situacao.where(pes.situacao != "", np.where(pes.dtp_pct.notna(), "abaixo", ""))
    cai = _years(sic / "caixa", ["cod_ibge", "ano", "periodicidade", "periodo", "liquida_livre"])
    cai = cai.sort_values(["cod_ibge", "ano", "periodicidade", "periodo"]).drop_duplicates(["cod_ibge", "ano"], keep="last")
    cai = cai.assign(ano=cai.ano.astype(int), liquida_livre=_num(cai.liquida_livre))
    fis = pes[["cod_ibge", "ano", "dtp_pct", "situacao", "rcl", "dtp"]].merge(cai[["cod_ibge", "ano", "liquida_livre"]], on=["cod_ibge", "ano"], how="outer")
    fis = fis[fis.cod_ibge.isin(codes)].sort_values(["cod_ibge", "ano"]).reset_index(drop=True)
    fis["situacao"] = fis.situacao.fillna("")
    fis["caixa_hab"] = fis.liquida_livre / fis.cod_ibge.map(pop)
    fis["uf"], fis["faixa"] = fis.cod_ibge.map(uf_of), fis.cod_ibge.map(band_of)
    con = _read(sic / "consultas.csv")
    read = set(zip(fis.cod_ibge, fis.ano.astype(str)))
    nf = con[(con.linhas == "0") & con.cod_ibge.isin(codes)] if len(con) else pd.DataFrame(columns=["cod_ibge", "ano"])
    nf = nf[[k not in read for k in zip(nf.cod_ibge, nf.ano)]]
    no_report = nf.groupby("cod_ibge").ano.apply(lambda s: sorted(int(y) for y in s)).to_dict() if len(nf) else {}

    # ---------------------------------------------------------- similar towns
    for t, col in ((em_hab, "v"), (fis, "dtp_pct"), (fis, "caixa_hab")):
        t[f"{col}_pu"] = percentile(t[col], [t.ano, t.uf])
        t[f"{col}_pb"] = percentile(t[col], [t.ano, t.faixa])
    c_hab["v_pu"], c_hab["v_pb"] = percentile(c_hab.v, [c_hab.uf]), percentile(c_hab.v, [c_hab.faixa])

    def medians(t: pd.DataFrame, col: str, by_year: bool = True) -> dict:
        res: dict = {}
        for g in ("uf", "faixa"):
            for k, v in t.dropna(subset=[col]).groupby(["ano", g] if by_year else [g])[col].median().items():
                if by_year:
                    res.setdefault(str(int(k[0])), {})[k[1]] = v
                else:
                    res[k[0] if isinstance(k, tuple) else k] = v
        return res
    # Amendments are compared over the last full year of payments.
    ref = last_year - 1 if len(pay) and pay[pay.ano == last_year].ano_mes.max() < f"{last_year}-12" else last_year

    # ---------------------------------------------------------- one record per town
    def lists(t: pd.DataFrame, by: str, cols: list[str]) -> dict[str, list]:
        res: dict[str, list] = {}
        for k, *row in t[[by, *cols]].astype(object).where(t[[by, *cols]].notna(), None).itertuples(index=False):
            res.setdefault(k, []).append(row)
        return res

    mayors = lists(pre.sort_values(["cod_ibge", "data_eleicao", "ano"]).assign(ano=lambda t: t.ano.astype(int), suplementar=lambda t: (t.suplementar == "1").astype(int)),
                   "cod_ibge", ["ano", "data_eleicao", "nome_urna", "partido", "suplementar"]) if len(pre) else {}
    y = yr[(yr.total.round() != 0) | (yr.privado.round() != 0)].reset_index()
    YEAR = ["total", *TIPOS, "municipal", "privado", "mesmo", "conhecido"]
    y[YEAR] = y[YEAR].apply(reais)
    years_of = lists(y, "cod_ibge", ["ano", *YEAR])
    authors = author_rows(gov, who, links)
    pa = gov[gov.partido_hoje != ""].groupby(["cod_ibge", "partido_hoje"]).valor.sum().reset_index()
    parties = lists(ranked(pa[pa.valor.round() != 0], "cod_ibge", "valor", "partido_hoje").assign(valor=lambda t: reais(t.valor)), "cod_ibge", ["partido_hoje", "valor"])
    k = gov[gov.ano >= MAYORS_FROM].groupby("cod_ibge")[["mesmo", "base", "conhecido"]].sum()
    k = k[k.conhecido > 0]
    own_party = {c: [r.mesmo / r.conhecido, r.base / r.conhecido, reais(r.conhecido)] for c, r in k.iterrows()}

    c_n, c_v = cm.groupby("municipio_ibge").size(), cm.groupby("municipio_ibge").v.sum()
    f = cm.groupby(["municipio_ibge", "fornecedor"]).agg(nome=("nome", "last"), n=("v", "size"), v=("v", "sum")).reset_index()
    f, _ = first_rows(ranked(f, "municipio_ibge", "v", "fornecedor"), "municipio_ibge", TOP_SUPPLIERS)
    reach_name = {v: k for k, v in REACH.items()}
    f["reach"] = [reach_name.get(reach.get(key), "") for key in zip(f.municipio_ibge, f.fornecedor)]
    suppliers = lists(f.assign(n=f.n.astype(int), v=reais(f.v)), "municipio_ibge", ["fornecedor", "nome", "n", "v", "reach"])
    t, _ = first_rows(ranked(cm, "municipio_ibge", "v", "controle"), "municipio_ibge", TOP_CONTRACTS)
    t = t.assign(data=t.assinatura.where(t.assinatura != "", t.publicacao), obj=t.objeto.str[:OBJ].where(t.nome != "", ""), v=reais(t.v))
    largest = lists(t, "municipio_ibge", ["data", "orgao", "nome", "obj", "v"])
    sg = sc.groupby(["municipio_ibge", "cobre"]).v.agg(["size", "sum"])
    by_reach: dict[str, dict] = {}
    for (cod, cobre), r in sg.iterrows():
        by_reach.setdefault(cod, {})[cobre] = [int(r["size"]), reais(r["sum"])]
    hit, _ = first_rows(ranked(sc[sc.cobre.isin(["sim", "possivel"])], "municipio_ibge", "v", "controle"), "municipio_ibge", TOP_BARRED)
    hit = hit.assign(obj=hit.objeto.str[:OBJ].where(hit.nome != "", ""), v=reais(hit.v))
    barred = lists(hit, "municipio_ibge", ["assinatura", "orgao", "fornecedor", "nome", "obj", "v", "cobre", "categoria_sancao", "orgao_sancionador"])

    fiscal = lists(fis.assign(ano=fis.ano.astype(int), rcl=reais(fis.rcl), dtp=reais(fis.dtp), liquida_livre=reais(fis.liquida_livre)), "cod_ibge", FISCAL)
    rk: dict[str, dict] = {c: {} for c in codes}
    if ref in years:
        for c, r in em_hab.xs(ref, level=1).iterrows():
            rk[c]["emendas_hab"] = [ref, r.v, r.v_pu, r.v_pb]
    for c, r in c_hab.iterrows():
        rk[c]["contratos_hab"] = [None, r.v, r.v_pu, r.v_pb]
    for col in ("dtp_pct", "caixa_hab"):
        for r in fis.dropna(subset=[col]).groupby("cod_ibge").tail(1).itertuples():
            rk[r.cod_ibge][col] = [int(r.ano), getattr(r, col), getattr(r, f"{col}_pu"), getattr(r, f"{col}_pb")]

    def record(r) -> dict:
        cod = r.cod_ibge
        return {"n": r.ente, "uf": r.uf, "p": None if pd.isna(r.habitantes) else int(r.habitantes), "k": r.faixa, "cap": int(r.capital == "1"),
                "m": mayors.get(cod, []),
                "a": {"y": years_of.get(cod, []), "au": authors.get(cod, []), "pa": parties.get(cod, []), "mp": own_party.get(cod)},
                "c": {"n": int(c_n.get(cod, 0)), "v": reais(c_v.get(cod, 0.0)), "x": int(left_out.get(cod, 0)), "f": suppliers.get(cod, []),
                      "t": largest.get(cod, []), "s": by_reach.get(cod, {}), "sl": barred.get(cod, [])},
                "f": {"y": fiscal.get(cod, []), "nf": no_report.get(cod, [])}, "r": rk[cod]}

    folder = out / "perfil"
    folder.mkdir(parents=True, exist_ok=True)
    keep = set()
    for prefix, g in e.groupby(e.cod_ibge.str[:4]):
        p = folder / f"{prefix}.json"
        write_json({r.cod_ibge: record(r) for r in g.itertuples()}, p, digits=4)
        keep.add(p.name)
    for p in folder.glob("*.json"):
        if p.name not in keep:
            p.unlink()
    csv(e[["cod_ibge", "ente", "uf", "populacao"]], out / "index.csv")

    # ---------------------------------------------------------- summary
    days = _read(src / "dias.csv")
    first, last = (days.dia.min(), days.dia.max()) if len(days) else ("", "")
    by_year = gov.groupby("ano").agg(total=("valor", "sum"), pix=("pix", "sum"), municipios=("cod_ibge", "nunique")).reset_index()
    r = {
        "towns": len(e), "tipos": TIPOS, "faixas": [s[2] for s in SIZES], "ano_ref": ref,
        "emendas": {"first": years[0] if years else None, "last_month": pay.ano_mes.max() if len(pay) else "", "by_year": by_year.to_dict("records"),
                    "prefeitura": float(gov[gov.alvo == "prefeitura"].valor.sum()), "municipal": float(gov[gov.alvo == "municipal"].valor.sum()),
                    "privado": float(pay[pay.alvo == "privado"].valor.sum())},
        "pncp": {"days_read": len(days), "first": first, "last": last, "since": START,
                 "span_days": (pd.Timestamp(last) - pd.Timestamp(START)).days + 1 if last else 0,
                 "contratos": len(cm), "valor": float(cm.v.sum()), "municipios": int(cm.municipio_ibge.nunique()),
                 "sancionados": {k: int((sc.cobre == k).sum()) for k in REACH}},
        "siconfi": {str(int(y)): int(n) for y, n in fis.dropna(subset=["dtp_pct"]).groupby("ano").size().items()},
        "peers": {"emendas_hab": medians(em_hab, "v"), "contratos_hab": medians(c_hab, "v", by_year=False),
                  "dtp_pct": medians(fis, "dtp_pct"), "caixa_hab": medians(fis, "caixa_hab")},
    }
    write_json(r, out / "resumo.json", digits=4)
    return {"towns": len(e), "amendment_rows": len(pay), "contracts": len(cm), "barred_contracts": len(sc), "shards": len(keep), "ano_ref": ref}
