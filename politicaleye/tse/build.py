"""Campaign finance of the general elections, as derived tables under ``data/tse/<year>/``.

    candidatos.csv              every candidate: office, state, party, result
    receitas_por_candidato.csv  each candidate's money by origin and by fund
    repasses_partidarios.csv    party organs' transfers to each candidate, by fund
    grandes_doadores.csv        private donors who gave at least DONOR_MIN in all, CPF masked
    doacoes_grandes_doadores.csv  what each of them gave to each candidate
    despesas_por_candidato.csv  each candidate's contracted and paid expenses
    fornecedores.csv            companies paid at least SUPPLIER_MIN in all, by CNPJ

The raw files (hundreds of MB to over a GB per election) stay in the cache;
only these tables are committed. Money is in reais with two decimals, summed
in centavos. ``methodology/tse.md`` explains every rule.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

from ..io import write_csv

DONOR_MIN = 50_000_00      # centavos: private donors listed by name
SUPPLIER_MIN = 50_000_00   # centavos: companies listed among suppliers
NULL = {"#NULO", "#NULO#", "-1", "-4", "#NE", "NÃO DIVULGÁVEL"}

ORIGENS = {   # DS_ORIGEM_RECEITA -> column
    "Recursos de partido político": "partido",
    "Recursos de pessoas físicas": "pessoas_fisicas",
    "Recursos de outros candidatos": "outros_candidatos",
    "Recursos próprios": "proprios",
    "Recursos de Financiamento Coletivo": "financiamento_coletivo",
    "Doações pela Internet": "internet",
}
FONTES = {"FUNDO ESPECIAL": "fefc", "FUNDO PARTIDARIO": "fundo_partidario", "OUTROS RECURSOS": "outros_recursos"}
CANDIDATOS = ["sq_candidato", "cargo", "uf", "ue", "numero", "nome", "nome_urna", "partido", "federacao",
              "situacao_candidatura", "resultado", "genero", "cor_raca", "ocupacao"]


def _log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


def cents(s: pd.Series) -> pd.Series:
    t = s.str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    t = t.where(t.str.fullmatch(r"-?\d+(\.\d+)?"), "0")
    neg = t.str.startswith("-")
    parts = t.str.lstrip("-").str.partition(".")
    out = parts[0].replace("", "0").astype("int64") * 100 + parts[2].str.ljust(2, "0").str[:2].astype("int64")
    return out.where(~neg, -out)


def reais(c: pd.Series) -> pd.Series:
    a = c.abs()
    return c.lt(0).map({True: "-", False: ""}) + (a // 100).astype(str) + "." + (a % 100).astype(str).str.zfill(2)


def mask_cpf(doc: str) -> str:
    d = re.sub(r"\D", "", doc)
    return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else ""


def _clean(s: pd.Series) -> pd.Series:
    s = s.str.strip()
    return s.where(~s.isin(NULL), "")


def _member(z: zipfile.ZipFile, prefix: str) -> str:
    names = [n for n in z.namelist() if n.startswith(prefix) and n.endswith("_BRASIL.csv")]
    if len(names) != 1:
        raise RuntimeError(f"{z.filename}: expected one {prefix}*_BRASIL.csv, found {names}")
    return names[0]


def _csv(z: zipfile.ZipFile, name: str, cols: list[str], chunksize: int | None = None):
    with z.open(name) as f:
        head = f.readline().decode("latin1")
    have = [c.strip().strip('"') for c in head.strip().split(";")]
    use = [c for c in cols if c in have]
    return pd.read_csv(z.open(name), sep=";", encoding="latin1", dtype=str, keep_default_na=False, usecols=use,
                       chunksize=chunksize)


def load_candidatos(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        c = _csv(z, _member(z, "consulta_cand_"), [
            "NR_TURNO", "SQ_CANDIDATO", "DS_CARGO", "SG_UF", "NM_UE", "NR_CANDIDATO", "NM_CANDIDATO",
            "NM_URNA_CANDIDATO", "SG_PARTIDO", "SG_FEDERACAO", "DS_SITUACAO_CANDIDATURA", "DS_SIT_TOT_TURNO",
            "DS_GENERO", "DS_COR_RACA", "DS_OCUPACAO"])
    c = c.apply(_clean)
    c["_t"] = pd.to_numeric(c.NR_TURNO, errors="coerce").fillna(0)
    c = c.sort_values(["SQ_CANDIDATO", "_t"]).drop_duplicates("SQ_CANDIDATO", keep="last")   # the last round's result
    out = pd.DataFrame({
        "sq_candidato": c.SQ_CANDIDATO, "cargo": c.DS_CARGO.str.title(), "uf": c.SG_UF, "ue": c.NM_UE,
        "numero": c.NR_CANDIDATO, "nome": c.NM_CANDIDATO, "nome_urna": c.NM_URNA_CANDIDATO, "partido": c.SG_PARTIDO,
        "federacao": c.get("SG_FEDERACAO", ""), "situacao_candidatura": c.DS_SITUACAO_CANDIDATURA,
        "resultado": c.DS_SIT_TOT_TURNO, "genero": c.DS_GENERO, "cor_raca": c.DS_COR_RACA, "ocupacao": c.DS_OCUPACAO,
    })
    return out.assign(_k=pd.to_numeric(out.sq_candidato)).sort_values("_k").drop(columns="_k")[CANDIDATOS]


def load_receitas(z: zipfile.ZipFile) -> pd.DataFrame:
    r = _csv(z, _member(z, "receitas_candidatos_2"), [
        "SQ_CANDIDATO", "SQ_PRESTADOR_CONTAS", "DS_ORIGEM_RECEITA", "DS_FONTE_RECEITA", "DS_NATUREZA_RECEITA",
        "NR_CPF_CNPJ_DOADOR", "NM_DOADOR", "SG_UF_DOADOR", "DS_ESFERA_PARTIDARIA_DOADOR", "SG_PARTIDO_DOADOR",
        "VR_RECEITA"])
    v = r.VR_RECEITA
    r = r.apply(_clean)
    r["v"] = cents(v)
    return r


def _wide(r: pd.DataFrame, col: str, mapping: dict[str, str], prefix: str) -> pd.DataFrame:
    k = r[col].map(mapping).fillna("outras")
    t = r.assign(_c=prefix + k).pivot_table(index="SQ_CANDIDATO", columns="_c", values="v", aggfunc="sum", fill_value=0)
    want = [prefix + v for v in mapping.values()] + [prefix + "outras"]
    return t.reindex(columns=want, fill_value=0)


def build_year(year: int, raw: Path, data: Path) -> dict:
    """Rebuild ``data/<year>/`` from the cached zips of that election."""
    out = data / str(year)
    cand = load_candidatos(raw / f"consulta_cand_{year}.zip")
    report = {"year": year, "candidatos": len(cand)}
    with zipfile.ZipFile(raw / f"prestacao_de_contas_eleitorais_candidatos_{year}.zip") as z:
        r = load_receitas(z)
        report["receitas_rows"] = len(r)

        # --- each candidate's money, by origin and by fund
        tot = r.groupby("SQ_CANDIDATO").v.sum().rename("total")
        fin = r[r.DS_NATUREZA_RECEITA == "FINANCEIRO"].groupby("SQ_CANDIDATO").v.sum().rename("financeiro")
        pf = r[r.DS_ORIGEM_RECEITA == "Recursos de pessoas físicas"]
        n_pf = pf.groupby("SQ_CANDIDATO").NR_CPF_CNPJ_DOADOR.nunique().rename("n_doadores_pf")
        by = pd.concat([tot, fin, _wide(r, "DS_ORIGEM_RECEITA", ORIGENS, "origem_"),
                        _wide(r, "DS_FONTE_RECEITA", FONTES, "fonte_"), n_pf], axis=1).fillna(0)
        money = [c for c in by.columns if c != "n_doadores_pf"]
        by = by.astype("int64").rename_axis("sq_candidato").reset_index()
        by = by.assign(_k=pd.to_numeric(by.sq_candidato)).sort_values("_k").drop(columns="_k")
        for c in money:
            by[c] = reais(by[c])
        write_csv(by, out / "receitas_por_candidato.csv")

        # --- party organs -> candidates
        p = r[r.DS_ORIGEM_RECEITA == "Recursos de partido político"]
        rep = (p.groupby(["SQ_CANDIDATO", "NR_CPF_CNPJ_DOADOR", "SG_PARTIDO_DOADOR", "DS_ESFERA_PARTIDARIA_DOADOR",
                          "SG_UF_DOADOR", "DS_FONTE_RECEITA"], as_index=False).v.sum()
               .rename(columns={"SQ_CANDIDATO": "sq_candidato", "NR_CPF_CNPJ_DOADOR": "cnpj_orgao",
                                "SG_PARTIDO_DOADOR": "partido", "DS_ESFERA_PARTIDARIA_DOADOR": "esfera",
                                "SG_UF_DOADOR": "uf_orgao", "DS_FONTE_RECEITA": "fonte", "v": "valor"}))
        rep["esfera"] = _clean(rep.esfera)
        rep = rep.assign(_k=pd.to_numeric(rep.sq_candidato)).sort_values(
            ["_k", "cnpj_orgao", "fonte"]).drop(columns="_k")
        rep["valor"] = reais(rep.valor)
        write_csv(rep, out / "repasses_partidarios.csv")

        # --- large private donors, CPF masked; grouped on the full CPF first
        pf = pf[pf.NR_CPF_CNPJ_DOADOR.str.fullmatch(r"\d{11}")]
        donor = pf.groupby("NR_CPF_CNPJ_DOADOR").agg(
            nome=("NM_DOADOR", lambda s: s.mode().sort_values().iloc[0]), uf=("SG_UF_DOADOR", "last"),
            total=("v", "sum"), n_candidatos=("SQ_CANDIDATO", "nunique"))
        big = donor[donor.total >= DONOR_MIN].copy()
        big["doador"] = big.index.map(mask_cpf)
        big = big.reset_index().sort_values(["total", "doador", "nome"], ascending=[False, True, True])
        gives = (pf[pf.NR_CPF_CNPJ_DOADOR.isin(big.NR_CPF_CNPJ_DOADOR)]
                 .groupby(["NR_CPF_CNPJ_DOADOR", "SQ_CANDIDATO"], as_index=False).v.sum()
                 .merge(big[["NR_CPF_CNPJ_DOADOR", "doador", "nome"]], on="NR_CPF_CNPJ_DOADOR"))
        gives = gives.assign(_t=gives.NR_CPF_CNPJ_DOADOR.map(big.set_index("NR_CPF_CNPJ_DOADOR").total),
                             _k=pd.to_numeric(gives.SQ_CANDIDATO))
        gives = gives.sort_values(["_t", "doador", "nome", "v", "_k"], ascending=[False, True, True, False, True])
        write_csv(big.assign(total=reais(big.total))[["doador", "nome", "uf", "total", "n_candidatos"]],
                  out / "grandes_doadores.csv")
        write_csv(pd.DataFrame({"doador": gives.doador, "nome": gives.nome, "sq_candidato": gives.SQ_CANDIDATO,
                                "valor": reais(gives.v)}), out / "doacoes_grandes_doadores.csv")
        report.update(doadores_pf=len(donor), grandes_doadores=len(big),
                      grandes_share=round(float(big.total.sum() / max(donor.total.sum(), 1)), 4))

        # --- expenses: contracted (with the candidate), paid (by account, joined through it)
        contracted, suppliers, accounts = [], [], set()
        for ch in _csv(z, _member(z, "despesas_contratadas_candidatos_"), [
                "SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO", "DS_TIPO_FORNECEDOR", "NR_CPF_CNPJ_FORNECEDOR",
                "NM_FORNECEDOR", "DS_CNAE_FORNECEDOR", "VR_DESPESA_CONTRATADA"], chunksize=500_000):
            ch["v"] = cents(ch.VR_DESPESA_CONTRATADA)
            contracted.append(ch.groupby("SQ_CANDIDATO").v.sum())
            accounts |= set(zip(ch.SQ_PRESTADOR_CONTAS, ch.SQ_CANDIDATO))
            co = ch[ch.NR_CPF_CNPJ_FORNECEDOR.str.fullmatch(r"\d{14}")]
            suppliers.append(co.groupby(["NR_CPF_CNPJ_FORNECEDOR", "NM_FORNECEDOR", "DS_CNAE_FORNECEDOR"]).agg(
                v=("v", "sum"), c=("SQ_CANDIDATO", lambda s: set(s))))
        accounts |= set(zip(r.SQ_PRESTADOR_CONTAS, r.SQ_CANDIDATO))
        acct = pd.DataFrame(sorted(accounts), columns=["SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO"])
        acct = acct.drop_duplicates("SQ_PRESTADOR_CONTAS")
        paid = []
        for ch in _csv(z, _member(z, "despesas_pagas_candidatos_"), ["SQ_PRESTADOR_CONTAS", "VR_PAGTO_DESPESA"],
                       chunksize=500_000):
            ch["v"] = cents(ch.VR_PAGTO_DESPESA)
            paid.append(ch.groupby("SQ_PRESTADOR_CONTAS").v.sum())
    con = pd.concat(contracted).groupby(level=0).sum().rename("contratado")
    pd_ = pd.concat(paid).groupby(level=0).sum().rename_axis("SQ_PRESTADOR_CONTAS").reset_index(name="pago")
    pd_ = pd_.merge(acct, on="SQ_PRESTADOR_CONTAS", how="left")
    report["despesas_pagas_sem_candidato"] = reais(pd.Series([int(pd_[pd_.SQ_CANDIDATO.isna()].pago.sum())])).iloc[0]
    pago = pd_.dropna(subset=["SQ_CANDIDATO"]).groupby("SQ_CANDIDATO").pago.sum()
    exp = pd.concat([con, pago], axis=1).fillna(0).astype("int64").rename_axis("sq_candidato").reset_index()
    exp = exp.assign(_k=pd.to_numeric(exp.sq_candidato, errors="coerce")).sort_values(["_k", "sq_candidato"]).drop(columns="_k")
    write_csv(exp.assign(contratado=reais(exp.contratado), pago=reais(exp.pago)), out / "despesas_por_candidato.csv")

    sup = pd.concat(suppliers).reset_index()
    sup = sup.groupby("NR_CPF_CNPJ_FORNECEDOR").agg(
        nome=("NM_FORNECEDOR", lambda s: s.mode().sort_values().iloc[0]),
        cnae=("DS_CNAE_FORNECEDOR", lambda s: s.mode().sort_values().iloc[0]),
        total=("v", "sum"), c=("c", lambda cs: set().union(*cs)))
    sup = sup[sup.total >= SUPPLIER_MIN].reset_index()
    sup["n_candidatos"] = sup.c.map(len)
    sup = sup.sort_values(["total", "NR_CPF_CNPJ_FORNECEDOR"], ascending=[False, True])
    write_csv(pd.DataFrame({"cnpj": sup.NR_CPF_CNPJ_FORNECEDOR, "nome": _clean(sup.nome), "cnae": _clean(sup.cnae),
                            "total": reais(sup.total), "n_candidatos": sup.n_candidatos}), out / "fornecedores.csv")
    write_csv(cand, out / "candidatos.csv")
    report.update(fornecedores=len(sup), candidatos_com_receita=int(len(by)))
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
