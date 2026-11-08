"""The contracts page's summaries on a tiny world: two towns, two mayors, one typo."""

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
    ]), d / "pncp" / "contratos" / "2025-03.csv")
    write_csv(pd.DataFrame([{"dia": "2025-03-01", "publicados": "10", "atualizados": "0"}]), d / "pncp" / "dias.csv")
    write_csv(pd.DataFrame([{"dia": "2025-03-01", "esfera": "M", "fornecedor_tipo": "PJ", "contratos": "8", "valor_global": "13000000.00"},
                            {"dia": "2025-03-01", "esfera": "F", "fornecedor_tipo": "PJ", "contratos": "2", "valor_global": "1500000.00"}]),
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
    assert r["coverage"]["days_read"] == 1 and r["totals"]["contratos"] == 10
    assert r["large"]["implausible"]["contratos"] == 1 and r["large"]["valor"] == 13_000_000      # the typo counts at 7 M
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
