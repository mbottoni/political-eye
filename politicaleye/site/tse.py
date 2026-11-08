"""Summaries for the campaign finance page: ``data/site/tse/<year>/``.

    resumo.csv         office: candidates, elected, money by origin and by fund, expenses contracted
    partidos.csv       office and party: candidates, women and Black candidates, money, public money, the share
                       of public money that went to women and to Black candidates, its Gini and top-10 share,
                       median public money for incumbents and for newcomers
    decis.csv          office and decile of money raised: candidates, elected
    candidatos.csv     federal deputy, senator, governor and president candidates: party, state, result,
                       gender, race, incumbency and money by origin and fund
    rede.json          the donor-candidate network of the 150 largest donors, laid out (spring layout, fixed seed)
    receptores.csv     the 300 candidates who got the most from donors of R$50,000 or more
    fornecedores.csv   the 300 companies paid the most

Public money: the Special Campaign Fund (FEFC) and the Party Fund. "Black" follows
the law's usage (pretos and pardos). See methodology/tse.md.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from .common import csv, write_json

OFFICES = ["Presidente", "Governador", "Senador", "Deputado Federal", "Deputado Estadual", "Deputado Distrital"]
SLIM = ["Presidente", "Governador", "Senador", "Deputado Federal"]
MONEY = ["total", "origem_partido", "origem_pessoas_fisicas", "origem_outros_candidatos", "origem_proprios",
         "origem_financiamento_coletivo", "fonte_fefc", "fonte_fundo_partidario"]
DONORS = 150


def layout(G: nx.Graph, iterations: int = 150, seed: int = 7, gravity: float = 4.0) -> dict:
    """Fruchterman-Reingold force layout in numpy (networkx needs scipy past 500 nodes), fixed seed.

    A pull toward the centre (gravity) keeps small separate groups from flying off
    and shrinking the main one to a dot once the drawing is scaled to fit."""
    nodes = sorted(G.nodes)
    n = len(nodes)
    if n == 0:
        return {}
    idx = {v: i for i, v in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1, 1, (n, 2))
    A = np.zeros((n, n))
    for u, v in G.edges:
        A[idx[u], idx[v]] = A[idx[v], idx[u]] = 1.0
    k = 1.0 / np.sqrt(n)
    t = 0.1
    for _ in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.maximum(np.linalg.norm(delta, axis=-1), 1e-3)
        force = (k * k / dist ** 2 - A * dist / k)[..., None] * delta
        disp = force.sum(1) - gravity * pos
        length = np.maximum(np.linalg.norm(disp, axis=-1), 1e-9)
        pos += disp / length[:, None] * np.minimum(length, t)[:, None]
        t -= 0.1 / (iterations + 1)
    pos -= pos.mean(0)
    pos /= np.abs(pos).max() or 1
    return {v: (round(float(pos[i, 0]), 4), round(float(pos[i, 1]), 4)) for v, i in idx.items()}


def gini(v: np.ndarray) -> float:
    v = np.sort(v[v > 0])
    n = len(v)
    if n == 0:
        return float("nan")
    return float(((2 * np.arange(1, n + 1) - n - 1) * v).sum() / (n * v.sum()))


def _incumbents(data: Path, year: int) -> set[str]:
    """TSE candidacies (sq) of people who sat in the Câmara in the legislature that ends with this election."""
    leg = (year - 1795) // 4   # the legislature in force in the election year (it ends the next 31 January)
    x = pd.read_csv(data / "ref" / "politicians.csv", dtype=str, keep_default_na=False)
    sitting = set()
    for f in (data / "camara" / "deputies").glob("*.csv"):
        y, m = int(f.stem[:4]), int(f.stem[5:7])
        if (y - (1 if m == 1 else 0) - 1795) // 4 == leg:
            sitting |= set(pd.read_csv(f, dtype=str, usecols=["deputado_id"]).deputado_id)
    people = set(x[(x.fonte == "camara") & x.id.isin(sitting)].pessoa)
    return set(x[(x.fonte == "tse") & x.pessoa.isin(people)].id)


def build_year(data: Path, year: int) -> dict:
    src, out = data / "tse" / str(year), data / "site" / "tse" / str(year)
    cand = pd.read_csv(src / "candidatos.csv", dtype=str, keep_default_na=False)
    rec = pd.read_csv(src / "receitas_por_candidato.csv", dtype=str, keep_default_na=False)
    for c in MONEY:
        rec[c] = pd.to_numeric(rec[c], errors="coerce").fillna(0)
    rec["n_doadores_pf"] = pd.to_numeric(rec.n_doadores_pf, errors="coerce").fillna(0).astype(int)
    c = cand[cand.cargo.isin(OFFICES)].merge(rec, on="sq_candidato", how="left")
    for k in MONEY:
        c[k] = c[k].fillna(0)
    c["n_doadores_pf"] = c.n_doadores_pf.fillna(0).astype(int)
    exp = pd.read_csv(src / "despesas_por_candidato.csv", dtype=str, keep_default_na=False)
    exp["contratado"] = pd.to_numeric(exp.contratado, errors="coerce").fillna(0)
    c = c.merge(exp[["sq_candidato", "contratado"]], on="sq_candidato", how="left").fillna({"contratado": 0})
    c["publico"] = c.fonte_fefc + c.fonte_fundo_partidario
    c["eleito"] = c.resultado.str.startswith("ELEITO")
    c["mulher"] = c.genero == "FEMININO"
    c["negro"] = c.cor_raca.isin(["PRETA", "PARDA"])
    inc = _incumbents(data, year)
    c["incumbente"] = c.sq_candidato.isin(inc) & (c.cargo == "Deputado Federal")

    agg = {k: (k, "sum") for k in [*MONEY, "publico", "contratado"]}
    res = c.groupby("cargo").agg(candidatos=("sq_candidato", "size"), eleitos=("eleito", "sum"), **agg).reindex(OFFICES).dropna(how="all").reset_index()
    csv(res.round(2), out / "resumo.csv")

    rows = []
    for (cargo, partido), g in c.groupby(["cargo", "partido"]):
        pub = g.publico.to_numpy()
        top = np.sort(pub)[::-1]
        dep = g[g.cargo == "Deputado Federal"]
        rows.append({
            "cargo": cargo, "partido": partido, "candidatos": len(g), "eleitos": int(g.eleito.sum()),
            "mulheres": int(g.mulher.sum()), "negros": int(g.negro.sum()), "total": g.total.sum(), "publico": pub.sum(),
            "publico_mulheres": g.loc[g.mulher, "publico"].sum(), "publico_negros": g.loc[g.negro, "publico"].sum(),
            "gini_publico": gini(pub), "top10_publico": top[:10].sum() / pub.sum() if pub.sum() > 0 else np.nan,
            "mediana_incumbentes": g.loc[g.incumbente, "publico"].median() if g.incumbente.any() else np.nan,
            "mediana_novos": g.loc[~g.incumbente, "publico"].median() if len(dep) else np.nan,
            "incumbentes": int(g.incumbente.sum()),
        })
    p = pd.DataFrame(rows)
    csv(p.round(4), out / "partidos.csv")

    dec = []
    for cargo, g in c[c.cargo.isin(["Deputado Federal", "Deputado Estadual", "Senador", "Governador"])].groupby("cargo"):
        g = g[g.situacao_candidatura.isin(["APTO", ""])]
        if len(g) < 20:
            continue
        q = pd.qcut(g.total.rank(method="first"), 10, labels=False) + 1
        for d, h in g.groupby(q):
            dec.append({"cargo": cargo, "decil": int(d), "candidatos": len(h), "eleitos": int(h.eleito.sum()),
                        "min": h.total.min(), "max": h.total.max(), "mediana": h.total.median()})
    csv(pd.DataFrame(dec).round(2), out / "decis.csv")

    slim = c[c.cargo.isin(SLIM)][["sq_candidato", "cargo", "uf", "nome_urna", "partido", "resultado", "genero", "cor_raca",
                                  "incumbente", "n_doadores_pf", *MONEY, "publico"]]
    slim = slim.assign(incumbente=slim.incumbente.astype(int)).round(2)
    csv(slim.sort_values(["cargo", "uf", "partido", "sq_candidato"]), out / "candidatos.csv")

    # Donor-candidate network: the largest donors, the candidates they funded.
    gd = pd.read_csv(src / "grandes_doadores.csv", dtype=str, keep_default_na=False)
    dd = pd.read_csv(src / "doacoes_grandes_doadores.csv", dtype=str, keep_default_na=False)
    gd["total"] = pd.to_numeric(gd.total)
    top = gd.sort_values("total", ascending=False).head(DONORS)
    key = top.doador + "|" + top.nome
    dd = dd[(dd.doador + "|" + dd.nome).isin(set(key))].assign(valor=lambda t: pd.to_numeric(t.valor))
    info = cand.set_index("sq_candidato")
    dd_all = pd.read_csv(src / "doacoes_grandes_doadores.csv", dtype=str, keep_default_na=False).assign(valor=lambda t: pd.to_numeric(t.valor))
    rc = dd_all.groupby("sq_candidato").agg(grandes_doadores=("doador", "size"), valor=("valor", "sum")).reset_index()
    rc = rc.merge(cand[["sq_candidato", "cargo", "uf", "nome_urna", "partido", "resultado"]], on="sq_candidato")
    rc = rc.sort_values(["valor", "sq_candidato"], ascending=[False, True]).head(300)
    csv(rc[["sq_candidato", "cargo", "uf", "nome_urna", "partido", "resultado", "grandes_doadores", "valor"]].round(2), out / "receptores.csv")
    G = nx.Graph()
    for k, r in zip(key, top.itertuples()):
        G.add_node(f"d:{k}", kind="doador", label=r.nome, valor=r.total, uf=r.uf)
    for r in dd.itertuples():
        s = r.sq_candidato
        if s not in info.index:
            continue
        i = info.loc[s]
        G.add_node(f"c:{s}", kind="candidato", label=i.nome_urna, partido=i.partido, cargo=i.cargo, uf=i.uf,
                   eleito=int(str(i.resultado).startswith("ELEITO")))
        G.add_edge(f"d:{r.doador}|{r.nome}", f"c:{s}", valor=r.valor)
    pos = layout(G)
    nodes = sorted(G.nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    write_json({
        "nodes": [{"id": n, **G.nodes[n], "x": float(pos[n][0]), "y": float(pos[n][1])} for n in nodes],
        "edges": sorted([idx[u], idx[v], d["valor"]] if idx[u] < idx[v] else [idx[v], idx[u], d["valor"]] for u, v, d in G.edges(data=True)),
    }, out / "rede.json", digits=3)

    f = pd.read_csv(src / "fornecedores.csv", dtype=str, keep_default_na=False)
    f["total"] = pd.to_numeric(f.total)
    csv(f.sort_values("total", ascending=False).head(300), out / "fornecedores.csv")
    return {"candidates": len(c), "parties": p.partido.nunique(), "incumbents": int(c.incumbente.sum()),
            "network": [G.number_of_nodes(), G.number_of_edges()]}


def build(data: Path) -> dict:
    years = sorted(int(p.name) for p in (data / "tse").iterdir() if p.is_dir() and p.name.isdigit())
    out = {y: build_year(data, y) for y in years}
    csv(pd.DataFrame({"ano": years}), data / "site" / "tse" / "anos.csv")
    return out
