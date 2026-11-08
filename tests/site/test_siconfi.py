"""The municipal finances page's summaries on two towns, one over the payroll limit."""

import json

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import siconfi as s


def world(tmp_path):
    d = tmp_path / "data"
    write_csv(pd.DataFrame([{"cod_ibge": "3500105", "ente": "Aldeia", "uf": "SP", "regiao": "SE", "populacao": "10000", "cnpj": "11111111000111", "capital": "0"},
                            {"cod_ibge": "3500204", "ente": "Bairro", "uf": "SP", "regiao": "SE", "populacao": "200000", "cnpj": "22222222000122", "capital": "0"}]),
              d / "siconfi" / "entes.csv")
    lim = {"limite_maximo_pct": "54.0", "limite_prudencial_pct": "51.3", "limite_alerta_pct": "48.6"}
    for y, a, b in ((2024, ("40.00", ""), ("52.00", "acima_prudencial")), (2025, ("44.00", ""), ("55.00", "acima_maximo"))):
        write_csv(pd.DataFrame([
            {"cod_ibge": "3500105", "ano": str(y), "periodicidade": "Q", "periodo": "3", "rcl": "100", "rcl_ajustada": "100", "dtp": a[0], "dtp_pct": a[0], **lim, "situacao": a[1]},
            {"cod_ibge": "3500204", "ano": str(y), "periodicidade": "Q", "periodo": "3", "rcl": "100", "rcl_ajustada": "100", "dtp": b[0], "dtp_pct": b[0], **lim, "situacao": b[1]},
        ]), d / "siconfi" / "pessoal" / f"{y}.csv")
    write_csv(pd.DataFrame([{"cod_ibge": "3500204", "ano": "2025", "periodicidade": "Q", "periodo": "3", "bruta_livre": "0", "liquida_livre": "-2000000",
                             "bruta_total": "0", "liquida_total": "0"}]), d / "siconfi" / "caixa" / "2025.csv")
    write_csv(pd.DataFrame([{"cod_ibge": c, "ano": y, "periodicidade": "Q", "periodo": "3", "linhas": "10", "consultado_em": "2026-11-07"}
                            for c in ("3500105", "3500204") for y in ("2024", "2025")]), d / "siconfi" / "consultas.csv")
    write_csv(pd.DataFrame([{"codigo": "P1", "ano": "2025", "tipo": "especial", "autor_codigo": "1", "autor": "X"},
                            {"codigo": "I1", "ano": "2025", "tipo": "individual", "autor_codigo": "1", "autor": "X"}]), d / "emendas" / "emendas" / "2025.csv")
    write_csv(pd.DataFrame([{"codigo_emenda": "P1", "ano_mes": "2025-05", "favorecido": "11111111000111", "tipo_favorecido": "", "uf": "", "municipio": "", "n_favorecidos": "1", "valor": "50000.00"},
                            {"codigo_emenda": "I1", "ano_mes": "2025-06", "favorecido": "11111111000111", "tipo_favorecido": "", "uf": "", "municipio": "", "n_favorecidos": "1", "valor": "30000.00"},
                            {"codigo_emenda": "I1", "ano_mes": "2025-06", "favorecido": "99999999000199", "tipo_favorecido": "", "uf": "", "municipio": "", "n_favorecidos": "1", "valor": "7.00"}]),
              d / "emendas" / "pagamentos" / "2025.csv")
    write_csv(pd.DataFrame([{"ano": "2024", "cod_ibge": c, "municipio": c, "uf": "SP", "sg_ue": "", "eleicao": "Eleições Municipais 2024", "data_eleicao": "2024-10-06",
                             "suplementar": "0", "turno": "1", "sq_candidato": c, "nome_urna": f"M{c}", "partido": p, "genero": "", "cor_raca": ""}
                            for c, p in (("3500105", "DEM"), ("3500204", "PT"))]), d / "ref" / "prefeitos.csv")
    return d


def test_size_class():
    assert s.size_class(pd.Series([100, 5000, 600000])).tolist() == ["under 5k", "5k–20k", "500k+"]


def test_build(tmp_path):
    d = world(tmp_path)
    s.build(d)
    out = d / "site" / "siconfi"
    r = json.loads((out / "resumo.json").read_text())
    st = {x["ano"]: x for x in r["status_by_year"]}
    assert st[2025]["acima_maximo"] == 1 and st[2025]["abaixo"] == 1 and st[2024]["acima_prudencial"] == 1
    assert r["cash_by_year"][0]["negativa"] == 1
    g = {x["ano"]: x for x in r["growth"]}
    assert abs(g[2025]["p50"] - ((44 / 40 - 1) + (55 / 52 - 1)) / 2) < 1e-4
    y = pd.read_csv(out / "anos" / "2025.csv", dtype={"cod_ibge": str}).set_index("cod_ibge")
    assert y.loc["3500105", "pix"] == 50000 and y.loc["3500105", "emendas"] == 80000 and y.loc["3500105", "pix_hab"] == 5.0
    assert y.loc["3500105", "partido_atual"] == "UNIÃO" and y.loc["3500204", "caixa_hab"] == -10.0
    pt = pd.read_csv(out / "partidos.csv").set_index(["ano", "partido"])
    assert pt.loc[(2025, "PT"), "maximo"] == 1 and pt.loc[(2025, "PT"), "caixa_negativa"] == 1
    town = json.loads((out / "uf" / "SP.json").read_text())["3500105"]
    assert town["a"] == [[2025, 80000.0, 50000.0]] and town["m"][0][1] == "DEM" and len(town["y"]) == 2


def test_build_is_deterministic(tmp_path):
    d = world(tmp_path)
    s.build(d)
    first = {f: f.read_bytes() for f in (d / "site").rglob("*") if f.is_file()}
    s.build(d)
    assert first == {f: f.read_bytes() for f in (d / "site").rglob("*") if f.is_file()}
