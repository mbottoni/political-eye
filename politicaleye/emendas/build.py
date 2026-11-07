"""Turn the amendments zip into tidy tables under ``data/emendas/``.

    data/emendas/emendas/YYYY.csv      amendments of year YYYY, by place and budget line, with the money
    data/emendas/pagamentos/YYYY.csv   who received it, month by month (private individuals summed, unnamed)
    data/emendas/convenios/YYYY.csv    the agreements that carry it
    data/emendas/favorecidos.csv       named recipients: CNPJ or government unit, name, legal nature
    data/emendas/por_autor.csv         totals by author, year and type
    data/emendas/por_municipio.csv     totals by municipality, year and type
    data/emendas/ref/*.csv             names of functions, programs, actions, budget plans, municipalities

All CSV, sorted, ``\\n`` line endings: a rebuild that changes nothing
produces no diff. Money is in reais with two decimals. ``methodology/emendas.md``
explains every rule.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

from ..io import write_csv
from .fetch import FILES

TIPOS = {
    "Emenda Individual - Transferências com Finalidade Definida": "individual",
    "Emenda Individual - Transferências Especiais": "especial",   # the "Pix" amendments
    "Emenda de Bancada": "bancada",
    "Emenda de Comissão": "comissao",
    "Emenda de Relator": "relator",
}
UNKNOWN = {"Sem informação", "S/I"}
MONEY = ["empenhado", "liquidado", "pago", "rap_inscritos", "rap_cancelados", "rap_pagos"]
EMENDAS = ["codigo", "ano", "tipo", "autor_codigo", "autor", "numero", "localidade", "municipio_ibge", "uf_ibge",
           "funcao", "subfuncao", "programa", "acao", "plano", *MONEY]
PAGAMENTOS = ["codigo_emenda", "ano_mes", "favorecido", "tipo_favorecido", "uf", "municipio", "n_favorecidos", "valor"]
CONVENIOS = ["codigo_emenda", "numero", "data_publicacao", "convenente", "objeto", "valor", "localidade",
             "funcao", "subfuncao"]
# Recipients named in the tables: legal entities (14-digit CNPJ), government
# units (6-digit UG code), the generic bank and payroll accounts (RB...), and
# foreign recipients (EX...) whose name carries a company or institution form.
# Everyone else, private individuals above all, is summed, unnamed.
NAMED = {"Pessoa Jurídica": re.compile(r"\d{14}"), "Unidade Gestora": re.compile(r"\d{6}")}
GENERIC = ("Inscrição Genérica", "Inscrição Genéric")   # the file spells it both ways
COMPANY = re.compile(
    r"\b(?:LTDA|LTD|LIMITED|INC|INCORPORATED|CORP|CORPORATION|COMPANY|CO|GMBH|AG|SA|S\.A|SAS|SRL|SPA|S\.P\.A|BV|B\.V"
    r"|NV|N\.V|AB|AS|A/S|LLC|L\.L\.C|LLP|PLC|PTY|KG|OY|SL|S\.L|SE|GROUP|HOLDING|INSTITUTE|INSTITUT|INSTITUTO"
    r"|UNIVERSITY|UNIVERSIDAD|UNIVERSIDADE|UNIVERSITE|FOUNDATION|FUNDACION|ASSOCIATION|SOCIETY|ORGANIZATION"
    r"|ORGANISATION|ORGANIZACAO|UNESCO|UNOPS|PNUD|UNICEF|OPAS|OMS|FAO|IICA|OCDE|CERN|EMBRAER)\b", re.I)


def _log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


def _read(z: zipfile.ZipFile, key: str) -> pd.DataFrame:
    with z.open(FILES[key]) as f:
        return pd.read_csv(f, sep=";", encoding="latin1", dtype=str, keep_default_na=False)


def cents(s: pd.Series) -> pd.Series:
    """``"1.450.000,00"`` or ``"1450000,00"`` -> 145000000 (integer centavos)."""
    t = s.str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    t = t.where(t != "", "0")
    neg = t.str.startswith("-")
    t = t.str.lstrip("-")
    parts = t.str.partition(".")
    whole, frac = parts[0].replace("", "0"), parts[2]
    out = whole.astype("int64") * 100 + frac.str.ljust(2, "0").str[:2].astype("int64")
    return out.where(~neg, -out)


def reais(c: pd.Series) -> pd.Series:
    """Integer centavos -> ``"1450000.00"``."""
    sign = c.lt(0).map({True: "-", False: ""})
    a = c.abs()
    return sign + (a // 100).astype(str) + "." + (a % 100).astype(str).str.zfill(2)


def _clean(s: pd.Series) -> pd.Series:
    s = s.str.strip()
    return s.where(~s.isin(UNKNOWN), "")


def load_emendas(z: zipfile.ZipFile) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict]:
    e = _read(z, "emendas")
    out = pd.DataFrame({
        "codigo": _clean(e["Código da Emenda"]),
        "ano": e["Ano da Emenda"].str.strip(),
        "tipo": e["Tipo de Emenda"].str.strip().map(lambda t: TIPOS.get(t, t)),
        "autor_codigo": _clean(e["Código do Autor da Emenda"]),
        "autor": _clean(e["Nome do Autor da Emenda"]),
        "numero": _clean(e["Número da emenda"]),
        "localidade": e["Localidade de aplicação do recurso"].str.strip(),
        "municipio_ibge": _clean(e["Código Município IBGE"]),
        "uf_ibge": _clean(e["Código UF IBGE"]),
        "funcao": e["Código Função"].str.strip(),
        "subfuncao": e["Código Subfunção"].str.strip(),
        "programa": e["Código Programa"].str.strip(),
        "acao": e["Código Ação"].str.strip(),
        "plano": e["Código Plano Orçamentário"].str.strip(),
    })
    for col, src in zip(MONEY, ["Valor Empenhado", "Valor Liquidado", "Valor Pago", "Valor Restos A Pagar Inscritos",
                                "Valor Restos A Pagar Cancelados", "Valor Restos A Pagar Pagos"]):
        out[col] = cents(e[src])

    def ref(cols: dict[str, str], key: list[str]) -> pd.DataFrame:
        r = pd.DataFrame({k: e[v].str.strip() for k, v in cols.items()})
        return r[r[key[-1]] != ""].drop_duplicates().sort_values(list(r.columns)).drop_duplicates(key, keep="last")

    refs = {
        "funcoes": ref({"funcao": "Código Função", "nome": "Nome Função"}, ["funcao"]),
        "subfuncoes": ref({"subfuncao": "Código Subfunção", "nome": "Nome Subfunção"}, ["subfuncao"]),
        "programas": ref({"programa": "Código Programa", "nome": "Nome Programa"}, ["programa"]),
        "acoes": ref({"acao": "Código Ação", "nome": "Nome Ação"}, ["acao"]),
        "planos": ref({"acao": "Código Ação", "plano": "Código Plano Orçamentário", "nome": "Nome Plano Orçamentário"},
                      ["acao", "plano"]),
        "municipios": ref({"municipio_ibge": "Código Município IBGE", "municipio": "Município", "uf_ibge": "Código UF IBGE",
                           "uf": "UF", "regiao": "Região"}, ["municipio_ibge"]),
    }
    refs["municipios"] = refs["municipios"][~refs["municipios"].municipio_ibge.isin(UNKNOWN)]
    report = {"emendas_rows": len(out), "emendas": int(out.codigo.replace("", pd.NA).nunique()),
              "emendas_without_code": int((out.codigo == "").sum()),
              "tipos_unmapped": int((~out.tipo.isin(TIPOS.values())).sum())}
    return out, refs, report


def load_pagamentos(z: zipfile.ZipFile) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    f = _read(z, "favorecidos")
    code = f["Código do Favorecido"].str.strip()
    tipo = f["Tipo Favorecido"].str.strip()
    named = pd.Series(False, index=f.index)
    for t, pat in NAMED.items():
        named |= (tipo == t) & code.str.fullmatch(pat)
    generic = tipo.isin(GENERIC)
    named |= generic & code.str.match(r"RB\d")
    named |= generic & code.str.startswith("EX") & f["Favorecido"].str.contains(COMPANY)
    am = f["Ano/Mês"].str.strip()
    p = pd.DataFrame({
        "codigo_emenda": _clean(f["Código da Emenda"]),
        "ano_mes": am.str[:4] + "-" + am.str[4:6],
        "favorecido": code.where(named, ""),
        "tipo_favorecido": tipo,
        "uf": f["UF Favorecido"].str.strip(),
        "municipio": f["Município Favorecido"].str.strip(),
        "valor": cents(f["Valor Recebido"]),
        "_code": code,
    })
    keys = ["codigo_emenda", "ano_mes", "tipo_favorecido", "uf", "municipio"]
    rest = p[~named].groupby(keys, as_index=False).agg(n_favorecidos=("_code", "nunique"), valor=("valor", "sum"))
    rest["favorecido"] = ""
    out = pd.concat([p[named].assign(n_favorecidos=1), rest], ignore_index=True)[PAGAMENTOS]

    # One name and legal nature per recipient: the most frequent, ties by name.
    who = pd.DataFrame({"favorecido": code, "nome": f["Favorecido"].str.strip(),
                        "natureza_juridica": f["Natureza Jurídica"].str.strip(), "tipo": tipo})[named]
    who = (who.value_counts().rename("n").reset_index()
           .sort_values(["favorecido", "n", "nome", "natureza_juridica"], ascending=[True, False, True, True])
           .drop_duplicates("favorecido")[["favorecido", "nome", "natureza_juridica", "tipo"]])
    report = {"pagamentos_rows": len(f), "pagamentos_named": int(named.sum()),
              "pagamentos_summed": int((~named).sum()), "pagamentos_summed_into": len(rest)}
    return out, who, report


def load_convenios(z: zipfile.ZipFile) -> tuple[pd.DataFrame, dict]:
    c = _read(z, "convenios")
    d = c["Data Publicação Convênio"].str.strip()
    out = pd.DataFrame({
        "codigo_emenda": _clean(c["Código da Emenda"]),
        "numero": c["Número Convênio"].str.strip(),
        "data_publicacao": d.str[6:10] + "-" + d.str[3:5] + "-" + d.str[0:2],
        "convenente": c["Convenente"].str.strip(),
        "objeto": c["Objeto Convênio"].str.split().str.join(" "),
        "valor": cents(c["Valor Convênio"]),
        "localidade": c["Localidade do gasto"].str.strip(),
        "funcao": c["Código Função"].str.strip(),
        "subfuncao": c["Código Subfunção"].str.strip(),
    })
    out.loc[d == "", "data_publicacao"] = ""
    return out, {"convenios_rows": len(out)}


def _money_out(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = reais(df[c])
    return df


def _write_by(df: pd.DataFrame, key: pd.Series, folder: Path, order: list[str], money: list[str]) -> set[Path]:
    written = set()
    df = df.assign(_k=key.to_numpy()).sort_values(order, kind="stable")
    for k, part in df.groupby("_k", sort=True):
        path = folder / f"{k}.csv"
        write_csv(_money_out(part.drop(columns="_k"), money), path)
        written.add(path)
    return written


def build(zip_path: Path, data: Path) -> dict:
    """Rebuild every table from the zip. Returns counts of what was summed or dropped."""
    with zipfile.ZipFile(zip_path) as z:
        em, refs, r1 = load_emendas(z)
        pg, who, r2 = load_pagamentos(z)
        cv, r3 = load_convenios(z)
    report = {**r1, **r2, **r3}

    keep = set()
    em_order = [c for c in EMENDAS if c not in MONEY] + MONEY
    keep |= _write_by(em, em.ano, data / "emendas", em_order, MONEY)
    keep |= _write_by(pg, pg.ano_mes.str[:4], data / "pagamentos",
                      ["ano_mes", "codigo_emenda", "favorecido", "tipo_favorecido", "uf", "municipio", "valor"], ["valor"])
    cv_year = cv.codigo_emenda.str[:4].where(cv.codigo_emenda.str.fullmatch(r"\d{4}.*"), "sem-ano")
    keep |= _write_by(cv, cv_year, data / "convenios", CONVENIOS, ["valor"])
    for sub in ("emendas", "pagamentos", "convenios"):
        for p in (data / sub).glob("*.csv"):
            if p not in keep:
                p.unlink()

    write_csv(who, data / "favorecidos.csv")
    for name, df in refs.items():
        write_csv(df, data / "ref" / f"{name}.csv")

    sums = {c: (c, "sum") for c in ("empenhado", "liquidado", "pago")}
    by_author = (em.groupby(["autor_codigo", "autor", "ano", "tipo"], as_index=False)
                 .agg(emendas=("codigo", "nunique"), **sums)
                 .sort_values(["autor_codigo", "autor", "ano", "tipo"]))
    write_csv(_money_out(by_author, list(sums)), data / "por_autor.csv")
    mun = em[em.municipio_ibge != ""]
    by_mun = (mun.groupby(["municipio_ibge", "ano", "tipo"], as_index=False)
              .agg(emendas=("codigo", "nunique"), **sums)
              .sort_values(["municipio_ibge", "ano", "tipo"]))
    write_csv(_money_out(by_mun, list(sums)), data / "por_municipio.csv")
    report.update(autores=int(em.autor_codigo.replace("", pd.NA).nunique()), favorecidos=len(who))
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
