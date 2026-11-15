"""The election tab: each deputy's outcome, the ranking's index, and the Chamber the election chose."""

import json

import numpy as np
import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import eleicao as el


def test_ranking_index_matches_the_ranking_page():
    # Four deputies of one state, a Speaker with no allowance spending, and a substitute with three months.
    r = pd.DataFrame({"deputado_id": ["1", "2", "3", "4", "160674", "9"], "uf": "SP", "meses": ["20"] * 5 + ["3"],
                      "presenca": ["0.9", "0.8", "0.7", "0.6", "0.05", "1"], "projetos_autor": ["4", "3", "2", "1", "0", "9"],
                      "relatorias": "1", "cota_mes": ["100", "200", "300", "400", "0", "1"]})
    s = el.ranking_index(r, 57)
    # Deputy 1: participation 87.5 (the Speaker is out of that pool), bills 90, opinions 50 (all tied), thrift 87.5.
    assert s.tolist()[:2] == [80.5, 61.5]
    assert s[4] == 30.0              # the Speaker: bills and opinions only
    assert np.isnan(s[5])            # under 12 months: not scored


def fixture(d):
    write_csv(pd.DataFrame({
        "pessoa": ["camara:1", "camara:2", "camara:3", "camara:4", "camara:5"], "deputado_id": ["1", "2", "3", "4", "5"],
        "nome": ["Ana", "Bia", "Caio", "Davi", "Eva"], "partido": ["PL", "PT", "PL", "PSD", "REPUBLIC"], "uf": "SP",
        "meses": ["40", "40", "40", "2", "40"], "presenca": ["0.9", "0.8", "0.7", "0.5", "0.6"],
        "emendas_pago": ["100.00", "80.00", "60.00", "0.00", "50.00"], "prefeito_mesmo_partido": ["0.5", "0.1", "0.2", "", "0.3"],
        "prefeito_base": ["0.2", "0.2", "0.2", "", "0.1"], "prefeito_mesmo_partido_valor": ["50.00", "8.00", "12.00", "", "15.00"],
    }), d / "site" / "deputados" / "deputados_57.csv")
    write_csv(pd.DataFrame({"deputado_id": ["1", "2", "3", "4", "5"], "uf": "SP", "meses": ["40", "40", "40", "2", "40"],
                            "presenca": ["0.9", "0.8", "0.7", "0.5", "0.6"], "projetos_autor": ["5", "4", "3", "0", "2"],
                            "relatorias": ["1", "1", "1", "0", "1"], "cota_mes": ["10", "20", "30", "0", "40"]}),
              d / "site" / "ranking" / "deputados_57.csv")
    # Caio registered for the Câmara, then ran for the Senate; Davi left; Eva ran for governor.
    # Fábio sat in the 56th legislature only; Gil has never sat.
    write_csv(pd.DataFrame({
        "pessoa": ["camara:1", "camara:2", "camara:3", "camara:3", "camara:5", "camara:6", "camara:6"],
        "fonte": ["tse"] * 6 + ["camara"], "id": ["s1", "s2", "s3a", "s3b", "s5", "s6", "6"], "nome": "x", "metodo": "",
    }), d / "ref" / "politicians.csv")
    cand = pd.DataFrame({
        "sq_candidato": ["s1", "s2", "s3a", "s3b", "s5", "s6", "s8"],
        "cargo": ["Deputado Federal", "Deputado Federal", "Deputado Federal", "Senador", "Governador", "Deputado Federal", "Deputado Federal"],
        "uf": "SP", "nome_urna": ["ANA", "BIA", "CAIO", "CAIO", "EVA", "FABIO", "GIL"],
        "partido": ["PL", "PT", "PL", "PL", "REPUBLICANOS", "PODE", "NOVO"], "federacao": "",
        "resultado": ["ELEITO POR QP", "SUPLENTE", "", "ELEITO", "NÃO ELEITO", "ELEITO POR MÉDIA", "ELEITO POR QP"],
        "genero": "FEMININO",
    })
    write_csv(cand, d / "tse" / "2026" / "candidatos.csv")
    write_csv(pd.DataFrame({"sq_candidato": ["s1", "s2", "s3b"], "total": ["1000.00", "800.00", "5000.00"]}), d / "tse" / "2026" / "receitas_por_candidato.csv")
    write_csv(pd.DataFrame({"sq_candidato": ["p1", "p2", "p3"], "cargo": "Deputado Federal", "partido": ["PL", "PSC", "PT"],
                            "resultado": ["ELEITO", "ELEITO POR QP", "SUPLENTE"]}), d / "tse" / "2022" / "candidatos.csv")
    dep = d / "camara" / "deputies"
    write_csv(pd.DataFrame({"deputado_id": ["6"], "nome": "Fábio", "partido": "PODE", "uf": "SP", "n_votes": 1, "n_authored": 0}), dep / "2022-05.csv")
    write_csv(pd.DataFrame({"deputado_id": ["1", "2", "3", "5", "99"], "nome": "x", "partido": ["PL", "PT", "PL", "REPUBLIC", ""],
                            "uf": ["SP", "SP", "SP", "SP", ""], "n_votes": 1, "n_authored": 0}), dep / "2026-10.csv")
    write_csv(pd.DataFrame({"deputado_id": ["1"], "nome": "x", "partido": "PL", "uf": "SP", "n_votes": 1, "n_authored": 0}), dep / "2026-11.csv")


def test_build(tmp_path):
    d = tmp_path / "data"
    fixture(d)
    r = el.build(d)[57]
    out = d / "site" / "eleicao"
    v = pd.read_csv(out / "deputados_57.csv", dtype=str, keep_default_na=False).set_index("nome")
    assert v.grupo.to_dict() == {"Ana": "reeleito", "Bia": "nao_reeleito", "Caio": "outro_eleito", "Davi": "nao_concorreu", "Eva": "outro_derrotado"}
    assert v.loc["Caio", ["cargo", "sq_candidato", "campanha_total"]].tolist() == ["Senador", "s3b", "5000.0"]   # the candidacy on the ballot
    assert v.loc["Eva", "partido_eleicao"] == "REPUBLICANOS" and v.loc["Davi", "partido_eleicao"] == "PSD"
    assert v.loc["Davi", "indice"] == ""                                     # two months: not scored
    assert r["grupos"]["reeleito"] == 1 and r["concorreram_camara"] == 2 and r["taxa_reeleicao"] == 0.5

    e = pd.read_csv(out / "eleitos_2026.csv", dtype=str, keep_default_na=False).set_index("nome_urna")
    assert e.origem.to_dict() == {"ANA": "reeleito", "FABIO": "ex_deputado", "GIL": "novo"}
    assert e.loc["FABIO", "deputado_id"] == "6" and e.loc["GIL", "deputado_id"] == ""
    assert r["ufs_pendentes"] == sorted(el.SEATS) and r["cadeiras_pendentes"] == 510   # three of SP's 70 seats, none elsewhere

    p = pd.read_csv(out / "partidos_2026.csv", dtype=str, keep_default_na=False).set_index("partido")
    assert p.loc["PODE", "eleitos_antes"] == "1"                             # PSC, merged into Podemos
    assert p.loc["REPUBLICANOS", "em_exercicio"] == "1"                      # the Câmara's short label, unified
    assert r["em_exercicio_mes"] == "2026-10" and r["em_exercicio"] == 4     # the election month; a former deputy's paper left out
    assert json.loads((out / "resumo.json").read_text())["legislaturas"] == [57]
