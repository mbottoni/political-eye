import json

import networkx as nx
import numpy as np
import pandas as pd

from politicaleye.site import tse as st


def w(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def fixture(d):
    """24 federal deputy candidates (odd sq: PT, even: PL), 1-8 women, 1-6 Black, 23 and 24 elected, 24 a sitting deputy."""
    sq = [str(i) for i in range(1, 25)]
    src = d / "tse" / "2022"
    w(src / "candidatos.csv", pd.DataFrame({
        "sq_candidato": [*sq, "99"], "cargo": ["Deputado Federal"] * 24 + ["Vice-Governador"], "uf": "SP", "ue": "SP", "numero": "1",
        "nome": [f"C{i}" for i in [*sq, "99"]], "nome_urna": [f"C{i}" for i in [*sq, "99"]], "partido": [("PT" if int(i) % 2 else "PL") for i in [*sq, "99"]],
        "federacao": "", "situacao_candidatura": "APTO", "resultado": ["NÃO ELEITO"] * 22 + ["ELEITO POR QP", "ELEITO POR MÉDIA", "NÃO ELEITO"],
        "genero": ["FEMININO"] * 8 + ["MASCULINO"] * 17, "cor_raca": ["PARDA"] * 6 + ["BRANCA"] * 19, "ocupacao": ""}))
    total = [int(i) * 1000 for i in sq]
    w(src / "receitas_por_candidato.csv", pd.DataFrame({
        "sq_candidato": sq, "total": total, "financeiro": total, "origem_partido": [t / 2 for t in total], "origem_pessoas_fisicas": [t / 2 for t in total],
        "origem_outros_candidatos": 0, "origem_proprios": 0, "origem_financiamento_coletivo": 0, "origem_internet": 0, "origem_outras": 0,
        "fonte_fefc": [t / 2 for t in total], "fonte_fundo_partidario": 0, "fonte_outros_recursos": [t / 2 for t in total], "fonte_outras": 0, "n_doadores_pf": 1}))
    w(src / "despesas_por_candidato.csv", pd.DataFrame({"sq_candidato": sq, "contratado": "100.00", "pago": "100.00"}))
    w(src / "grandes_doadores.csv", pd.DataFrame({"doador": ["***.111.111-**", "***.222.222-**"], "nome": ["ANA", "BIA"], "uf": "", "total": [300000, 100000], "n_candidatos": [2, 1]}))
    w(src / "doacoes_grandes_doadores.csv", pd.DataFrame({"doador": ["***.111.111-**", "***.111.111-**", "***.222.222-**"], "nome": ["ANA", "ANA", "BIA"],
                                                          "sq_candidato": ["1", "2", "2"], "valor": [100000, 200000, 100000]}))
    w(src / "fornecedores.csv", pd.DataFrame({"cnpj": ["00000000000191"], "nome": ["GRAFICA"], "cnae": ["Impressão"], "total": [500000], "n_candidatos": [3]}))
    w(d / "ref" / "politicians.csv", pd.DataFrame({"pessoa": ["camara:9", "camara:9"], "fonte": ["camara", "tse"], "id": ["9", "24"], "nome": ["C24", "C24"], "metodo": ["", "x"]}))
    w(d / "camara" / "deputies" / "2022-03.csv", pd.DataFrame({"deputado_id": ["9"], "nome": ["C24"], "partido": ["PL"], "uf": ["SP"], "n_votes": [1], "n_authored": [0]}))


def test_build(tmp_path):
    fixture(tmp_path)
    r = st.build(tmp_path)
    assert r[2022]["candidates"] == 24 and r[2022]["incumbents"] == 1 and r[2022]["network"] == [4, 3]
    out = tmp_path / "site" / "tse" / "2022"
    res = pd.read_csv(out / "resumo.csv").set_index("cargo").loc["Deputado Federal"]
    assert (res.candidatos, res.eleitos, res.total, res.publico, res.contratado) == (24, 2, 300000, 150000, 2400)

    p = pd.read_csv(out / "partidos.csv").set_index("partido")
    assert (p.loc["PT", "candidatos"], p.loc["PT", "mulheres"], p.loc["PT", "negros"]) == (12, 4, 3)
    assert p.loc["PT", "publico_mulheres"] == (1 + 3 + 5 + 7) * 500
    assert round(p.loc["PT", "top10_publico"], 4) == round(140 / 144, 4)   # its ten best funded leave out 1 and 3
    assert (p.loc["PL", "incumbentes"], p.loc["PL", "mediana_incumbentes"], p.loc["PL", "mediana_novos"]) == (1, 12000, 6000)
    assert p.loc["PT", "incumbentes"] == 0 and np.isnan(p.loc["PT", "mediana_incumbentes"])

    dec = pd.read_csv(out / "decis.csv")
    assert dec.candidatos.sum() == 24 and dec.decil.tolist() == list(range(1, 11))
    assert dec.set_index("decil").loc[10, "eleitos"] == 2                   # the two winners raised the most

    cand = pd.read_csv(out / "candidatos.csv", dtype=str).set_index("sq_candidato")
    assert "99" not in cand.index and cand.loc["24", "incumbente"] == "1" and cand.loc["23", "incumbente"] == "0"

    rec = pd.read_csv(out / "receptores.csv", dtype=str)
    assert rec.iloc[0][["sq_candidato", "grandes_doadores"]].tolist() == ["2", "2"] and float(rec.iloc[0].valor) == 300000

    net = json.loads((out / "rede.json").read_text())
    kinds = sorted(n["kind"] for n in net["nodes"])
    assert kinds == ["candidato", "candidato", "doador", "doador"] and len(net["edges"]) == 3
    assert all(-1 <= n["x"] <= 1 and -1 <= n["y"] <= 1 for n in net["nodes"])
    assert all(n["id"].startswith("d:***.") for n in net["nodes"] if n["kind"] == "doador")   # CPFs stay masked
    assert pd.read_csv(tmp_path / "site" / "tse" / "anos.csv").ano.tolist() == [2022]


def test_rebuild_is_identical(tmp_path):
    fixture(tmp_path)
    st.build(tmp_path)
    out = tmp_path / "site" / "tse" / "2022"
    first = {f.name: f.read_bytes() for f in out.iterdir()}
    st.build(tmp_path)
    assert {f.name: f.read_bytes() for f in out.iterdir()} == first


def test_gini_and_layout():
    assert st.gini(np.array([5.0, 5.0, 5.0])) == 0
    assert st.gini(np.array([1.0, 3.0])) == 0.25
    assert st.gini(np.array([0.0, 2.0])) == 0                 # zeros are left out
    G = nx.Graph([(0, 1), (1, 2), (3, 4)])
    a, b = st.layout(G), st.layout(G)
    assert a == b and set(a) == {0, 1, 2, 3, 4}
    assert max(max(abs(x), abs(y)) for x, y in a.values()) == 1
