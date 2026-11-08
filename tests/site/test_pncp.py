"""The contracts page's summaries on a tiny world: two towns, two mayors, and typos of each kind."""

import json

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import pncp as p

COLS = ["controle", "compra", "publicacao", "assinatura", "vigencia_inicio", "vigencia_fim", "orgao_cnpj", "orgao", "esfera", "poder", "uf",
        "municipio_ibge", "tipo", "categoria", "fornecedor_tipo", "fornecedor", "fornecedor_nome", "objeto", "valor_inicial", "valor_global",
        "retificacao"]


def contract(ctrl, day, buyer, esfera, town, supplier, value, initial=None):
    r = dict.fromkeys(COLS, "")
    r.update(controle=ctrl, publicacao=day, assinatura=day, orgao_cnpj=buyer, orgao=f"BODY {buyer}", esfera=esfera, uf="SP",
             municipio_ibge=town, categoria="Obras", fornecedor_tipo="PJ", fornecedor=supplier, fornecedor_nome=f"CO {supplier}",
             objeto="X" * 300, valor_inicial=str(initial if initial is not None else value), valor_global=str(value))
    return r


def world(tmp_path):
    d = tmp_path / "data"
    write_csv(pd.DataFrame([
        contract("a", "2025-03-01", "B1", "M", "3500105", "S1", 2_000_000),
        contract("b", "2025-03-01", "B1", "M", "3500105", "S1", 3_000_000),
        contract("c", "2025-03-01", "B2", "M", "3500204", "S2", 45_000_000_000, initial=7_000_000),   # a typo
        contract("d", "2025-03-01", "B3", "F", "5300108", "S3", 1_000_000),
        contract("e", "2025-03-01", "B1", "M", "3500105", "S4", 900_000_000),          # 4.5 years of town A's revenue
        contract("f", "2025-03-01", "B3", "F", "5300108", "S5", 2_800_000_000_000),    # R$ 2.8 trillion
    ]), d / "pncp" / "contratos" / "2025-03.csv")
    write_csv(pd.DataFrame([{"cod_ibge": "3500105", "ano": "2025", "periodicidade": "Q", "periodo": "1", "rcl": "100000000", "rcl_ajustada": "",
                             "dtp": "", "dtp_pct": "", "limite_maximo_pct": "", "limite_prudencial_pct": "", "limite_alerta_pct": "", "situacao": ""},
                            {"cod_ibge": "3500105", "ano": "2025", "periodicidade": "Q", "periodo": "3", "rcl": "190000000", "rcl_ajustada": "200000000",
                             "dtp": "", "dtp_pct": "", "limite_maximo_pct": "", "limite_prudencial_pct": "", "limite_alerta_pct": "", "situacao": ""}]),
              d / "siconfi" / "pessoal" / "2025.csv")
    write_csv(pd.DataFrame([{"dia": "2025-03-01", "publicados": "10", "atualizados": "0"}]), d / "pncp" / "dias.csv")
    write_csv(pd.DataFrame([{"dia": "2025-03-01", "esfera": "M", "fornecedor_tipo": "PJ", "contratos": "9", "valor_global": "45913000000.00"},
                            {"dia": "2025-03-01", "esfera": "F", "fornecedor_tipo": "PJ", "contratos": "3", "valor_global": "2800001500000.00"}]),
              d / "pncp" / "resumo_dia.csv")
    write_csv(pd.DataFrame([{"cod_ibge": "3500105", "ente": "A", "uf": "SP", "regiao": "SE", "populacao": "1000", "cnpj": "", "capital": "0"},
                            {"cod_ibge": "3500204", "ente": "B", "uf": "SP", "regiao": "SE", "populacao": "3000", "cnpj": "", "capital": "0"}]),
              d / "siconfi" / "entes.csv")
    pre = [{"ano": "2024", "cod_ibge": t, "municipio": t, "uf": "SP", "sg_ue": "", "eleicao": "Eleições Municipais 2024", "data_eleicao": "2024-10-06",
            "suplementar": "0", "turno": "1", "sq_candidato": t, "nome_urna": f"M {t}", "partido": party, "genero": "", "cor_raca": ""}
           for t, party in (("3500105", "PMDB"), ("3500204", "PT"))]
    write_csv(pd.DataFrame(pre), d / "ref" / "prefeitos.csv")
    return d


def test_gini_and_hhi():
    assert p.gini([1, 1, 1, 1]) == 0.0 and abs(p.gini([0, 0, 0, 10]) - 0.0) < 1e-9   # zeros are left out
    assert abs(p.gini([1, 3]) - 0.25) < 1e-9
    assert p.hhi(pd.Series([0.5, 0.5])) == 0.5


def test_build(tmp_path):
    d = world(tmp_path)
    p.build(d)
    out = d / "site" / "pncp"
    r = json.loads((out / "resumo.json").read_text())
    assert r["coverage"]["days_read"] == 1 and r["totals"]["contratos"] == 12
    assert r["large"]["implausible"]["contratos"] == 1 and r["large"]["valor"] == 13_000_000      # the typo counts at 7 M
    # The two values with nothing to trust are left out everywhere, and the daily totals lose what every typo added.
    assert r["large"]["left_out"]["contratos"] == 2 and r["large"]["left_out"]["publicado"] == 2_800_900_000_000
    assert abs(r["totals"]["valor"] - (12_000_000 + 8_000_000 + 1_500_000)) < 1e-3   # municipal: large 12 M, small 8 M
    gone = pd.read_csv(out / "descartados.csv").set_index("controle")
    assert list(gone.index) == ["f", "e"] and gone.loc["e", "receita"] == 200_000_000 and pd.isna(gone.loc["f", "receita"])
    assert {"e", "f"}.isdisjoint(pd.read_csv(out / "maiores.csv").controle) and "S4" not in set(pd.read_csv(out / "fornecedores.csv").cnpj)
    top = pd.read_csv(out / "maiores.csv")
    assert top.objeto.str.len().max() == p.OBJ and top.loc[top.controle == "c", "suspeito"].item() == 1
    # Mayors' parties, under today's names, per inhabitant-year of 2025.
    pt = pd.read_csv(out / "partidos.csv").set_index("partido")
    assert pt.loc["MDB", "valor"] == 5_000_000 and pt.loc["MDB", "pop_anos"] == 1000 and pt.loc["MDB", "por_habitante_ano"] == 5000
    assert pt.loc["PT", "valor"] == 7_000_000 and pt.loc["PT", "contratos"] == 1
    mun = pd.read_csv(out / "municipios.csv", dtype={"cod_ibge": str}).set_index("cod_ibge")
    assert "5300108" not in mun.index and mun.loc["3500105", "por_habitante"] == 5000   # only municipal bodies
    org = pd.read_csv(out / "orgaos.csv").set_index("orgao_cnpj")
    assert org.loc["B1", "maior_share"] == 1.0


def test_build_is_deterministic(tmp_path):
    d = world(tmp_path)
    p.build(d)
    first = {f: f.read_bytes() for f in (d / "site").rglob("*") if f.is_file()}
    p.build(d)
    assert first == {f: f.read_bytes() for f in (d / "site").rglob("*") if f.is_file()}


def test_plausible():
    c = pd.DataFrame({"valor_inicial": ["7000000", "0", "500000000", "20000000000", "1000000"],
                      "valor_global": ["45000000000", "1129000000000", "500000000", "20000000000", "1000000"],
                      "esfera": ["F", "M", "M", "E", "M"], "municipio_ibge": ["", "2603900", "2603900", "", "9999999"]})
    got = p.plausible(c, pd.Series({"2603900": 131_000_000.0}))
    # the 15x rule; no initial and 8,600 years of revenue; 3.8 years of revenue; over R$ 10 bn; a town with no report read
    assert got.suspeito.tolist() == [1, 2, 2, 2, 0] and got.v.tolist() == [7_000_000, 0, 0, 0, 1_000_000]
