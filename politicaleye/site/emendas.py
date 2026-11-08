"""Summaries for the parliamentary amendments page: ``data/site/emendas/``.

    anos.csv          year and type: amendments, committed, settled, paid
    ufs.csv           year, type and state of application: committed, paid (empty state: national)
    autores.csv       author code: the person, house, party and state they link to (data/ref/politicians.csv)
    autor_uf.csv      author code and year: paid in all, paid in the author's own state, paid nationally
    fluxos.csv        year, author's state and destination state: paid
    meses.csv         payment month and type: paid to recipients (from the payments table)
    municipios.csv    payment year and the recipient's municipality (IBGE code): paid, and paid by "Pix"
    natureza.csv      year and legal nature of the recipient: paid
    favorecidos.csv   the 1,000 named recipients paid the most: total, by year, amendments

Amounts in reais with two decimals, summed in centavos. See methodology/emendas.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import csv

TOP_RECIPIENTS = 1000
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE",
      "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
      "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
RENAMED = {   # (name in the payment file, UF) -> name in IBGE's list
    ("EMBU", "SP"): "Embu das Artes", ("SANTA ISABEL DO PARÁ", "PA"): "Santa Izabel do Pará",
    ("PRESIDENTE JUSCELINO", "RN"): "Serra Caiada", ("SANTANA DO LIVRAMENTO", "RS"): "Sant'Ana do Livramento",
    ("ITAPAGÉ", "CE"): "Itapajé", ("ELDORADO DOS CARAJÁS", "PA"): "Eldorado do Carajás", ("IGUARACI", "PE"): "Iguaracy",
    ("FORTALEZA DO TABOCÃO", "TO"): "Tabocão",
}


def _cents(s: pd.Series) -> pd.Series:
    return (pd.to_numeric(s, errors="coerce").fillna(0) * 100).round().astype("int64")


def _reais(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        v = df[c].astype("int64")
        df[c] = (v // 100).astype(str) + "." + (v.abs() % 100).astype(str).str.zfill(2)
        df.loc[v < 0, c] = "-" + ((-v) // 100).astype(str) + "." + ((-v) % 100).astype(str).str.zfill(2)
    return df


def _years(folder: Path) -> pd.DataFrame:
    return pd.concat([pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted(folder.glob("*.csv"))],
                     ignore_index=True)


def _people(data: Path) -> pd.DataFrame:
    """Author code -> person, house, latest party and state, from the crosswalk and the chambers' tables."""
    x = pd.read_csv(data / "ref" / "politicians.csv", dtype=str, keep_default_na=False)
    au = x[x.fonte == "emendas"][["id", "pessoa"]].rename(columns={"id": "autor_codigo"})
    info = []
    for fonte, folder, key in (("camara", data / "camara" / "deputies", "deputado_id"), ("senado", data / "senado" / "senators", "senador_id")):
        files = sorted(folder.glob("*.csv"))   # every month: the latest label wins
        if not files:
            continue
        t = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False).assign(_m=f.stem) for f in files])
        t = t[t.partido != ""].sort_values("_m").groupby(key)[["partido", "uf", "_m"]].last().reset_index()
        ids = x[x.fonte == fonte][["id", "pessoa"]]
        info.append(t.merge(ids, left_on=key, right_on="id")[["pessoa", "partido", "uf", "_m"]].assign(casa=fonte))
    from ..camara.orientations import party_key
    inf = pd.concat(info).sort_values("_m").groupby("pessoa")[["partido", "uf", "casa"]].last().reset_index()
    inf["partido"] = inf.partido.map(party_key)   # one label per party (REPUBLIC, REPUBLICANOS -> REPUBLICANOS)
    names = x.sort_values("fonte").groupby("pessoa").nome.first()
    out = au.merge(inf, on="pessoa", how="left").assign(nome=lambda t: t.pessoa.map(names))
    return out.fillna("")


def town_codes(data: Path, pg: pd.DataFrame) -> list[str]:
    """IBGE code of each payment's recipient municipality, matched on name and state ("" if none matches)."""
    from ..ref.politicians import norm
    ref = pd.read_csv(data / "siconfi" / "entes.csv", dtype=str, keep_default_na=False)   # state as a two-letter code
    code = {(norm(r.ente), r.uf): r.cod_ibge for r in ref.itertuples()}
    for (old_name, uf), new_name in RENAMED.items():   # towns renamed since: the payment file keeps the old name
        if (norm(new_name), uf) in code:
            code[(norm(old_name), uf)] = code[(norm(new_name), uf)]
    return [code.get((norm(m), u), "") for m, u in zip(pg.municipio, pg.uf)]


def build(data: Path) -> dict:
    out = data / "site" / "emendas"
    em = _years(data / "emendas" / "emendas")
    for c in ("empenhado", "liquidado", "pago"):
        em[c] = _cents(em[c])

    anos = em.groupby(["ano", "tipo"]).agg(emendas=("codigo", lambda s: s[s != ""].nunique()), empenhado=("empenhado", "sum"),
                                           liquidado=("liquidado", "sum"), pago=("pago", "sum")).reset_index()
    csv(_reais(anos, ["empenhado", "liquidado", "pago"]), out / "anos.csv")

    em["uf"] = em.uf_ibge.str[:2].map(UF).fillna("")   # IBGE state code (2200000) -> two letters (PI)
    ufs = em.groupby(["ano", "tipo", "uf"])[["empenhado", "pago"]].sum().reset_index()
    csv(_reais(ufs, ["empenhado", "pago"]), out / "ufs.csv")

    people = _people(data)
    csv(people.sort_values("autor_codigo"), out / "autores.csv")
    au_uf = em.merge(people[["autor_codigo", "uf"]].rename(columns={"uf": "uf_autor"}), on="autor_codigo", how="left")
    au_uf["uf_autor"] = au_uf.uf_autor.fillna("")
    linked = au_uf[au_uf.uf_autor != ""]
    by = linked.groupby(["autor_codigo", "ano"]).agg(pago=("pago", "sum")).join(
        linked[linked.uf == linked.uf_autor].groupby(["autor_codigo", "ano"]).pago.sum().rename("pago_estado")).join(
        linked[linked.uf == ""].groupby(["autor_codigo", "ano"]).pago.sum().rename("pago_nacional")).fillna(0).reset_index()
    csv(_reais(by, ["pago", "pago_estado", "pago_nacional"]), out / "autor_uf.csv")
    fl = linked.groupby(["ano", "uf_autor", "uf"]).pago.sum().reset_index().rename(columns={"uf": "uf_destino"})
    csv(_reais(fl[fl.pago != 0], ["pago"]), out / "fluxos.csv")

    pg = _years(data / "emendas" / "pagamentos")
    pg["valor"] = _cents(pg.valor)
    tipo = em.drop_duplicates("codigo").set_index("codigo").tipo
    pg["tipo"] = pg.codigo_emenda.map(tipo).fillna("sem código")
    meses = pg.groupby(["ano_mes", "tipo"]).valor.sum().reset_index()
    csv(_reais(meses, ["valor"]), out / "meses.csv")

    # Where the money landed: the recipient's municipality, matched by name and state to its IBGE code.
    pg["ibge"] = town_codes(data, pg)
    mun = pg[pg.ibge != ""].assign(ano=lambda t: t.ano_mes.str[:4], pix=lambda t: t.valor.where(t.tipo == "especial", 0))
    mun = mun.groupby(["ano", "ibge"]).agg(valor=("valor", "sum"), pix=("pix", "sum")).reset_index().rename(columns={"ibge": "municipio_ibge"})
    csv(_reais(mun[mun.valor != 0], ["valor", "pix"]), out / "municipios.csv")
    matched = float(pg.loc[pg.ibge != "", "valor"].sum() / max(pg.valor.sum(), 1))

    who = pd.read_csv(data / "emendas" / "favorecidos.csv", dtype=str, keep_default_na=False).set_index("favorecido")
    pg["natureza"] = pg.favorecido.map(who.natureza_juridica).where(pg.favorecido != "", pg.tipo_favorecido)
    pg["natureza"] = pg.natureza.replace("", "Sem informação")
    nat = pg.groupby([pg.ano_mes.str[:4].rename("ano"), "natureza"]).valor.sum().reset_index()
    csv(_reais(nat, ["valor"]), out / "natureza.csv")

    named = pg[pg.favorecido != ""]
    tot = named.groupby("favorecido").agg(total=("valor", "sum"), emendas=("codigo_emenda", "nunique"),
                                          primeiro=("ano_mes", "min"), ultimo=("ano_mes", "max"))
    top = tot.sort_values("total", ascending=False).head(TOP_RECIPIENTS)
    top = top.join(who[["nome", "natureza_juridica", "tipo"]]).reset_index()
    uf_of = named.groupby("favorecido").uf.agg(lambda s: s.mode().iloc[0])
    top["uf"] = top.favorecido.map(uf_of)
    top = top[["favorecido", "nome", "natureza_juridica", "uf", "emendas", "primeiro", "ultimo", "total"]]
    csv(_reais(top, ["total"]), out / "favorecidos.csv")
    return {"years": em.ano.nunique(), "authors": len(people), "authors_linked": int((people.casa != "").sum()),
            "flows": len(fl), "months": meses.ano_mes.nunique(), "paid_matched_to_a_town": round(matched, 4)}
