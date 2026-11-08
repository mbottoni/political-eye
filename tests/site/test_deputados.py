import numpy as np
import pandas as pd

from politicaleye.camara import graphs
from politicaleye.camara.build import build_year
from politicaleye.site import deputados as sd
from politicaleye.views.deputados import COLS
from tests.camara.conftest import write_raw_2025


def w(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def fixture(tmp_path):
    raw, d = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)                       # deputies 10, 20, 30, 40 voting in March and April 2025
    build_year(2025, raw, d / "camara")
    graphs._load.cache_clear()
    view = pd.DataFrame({c: "" for c in COLS}, index=range(4))
    view["deputado_id"] = ["10", "20", "30", "40"]
    view["pessoa"] = "camara:" + view.deputado_id
    view["nome"] = ["Dez", "Vinte", "Trinta", "Quarenta"]
    view["partido"], view["uf"] = ["P1", "B", "P1", "P1"], "SP"
    view.loc[0, ["campanha_sq_candidato", "campanha_total"]] = ["s10", "1000.00"]
    w(d / "views" / "deputados_57.csv", view)
    w(d / "ref" / "politicians.csv", pd.DataFrame({"pessoa": ["camara:10", "camara:10"], "fonte": ["camara", "emendas"], "id": ["10", "900"], "nome": "Dez", "metodo": ""}))
    w(d / "emendas" / "emendas" / "2024.csv", pd.DataFrame({
        "codigo": ["E1", "E2", "E3"], "ano": "2024", "tipo": ["individual", "especial", "individual"], "autor_codigo": ["900", "900", "777"],
        "autor": "x", "numero": "1", "localidade": "x", "municipio_ibge": "", "uf_ibge": ["3500000", "", "3500000"], "funcao": "1", "subfuncao": "1",
        "programa": "1", "acao": "1", "plano": "1", "empenhado": ["100.00", "20.00", "5.00"], "liquidado": "0", "pago": ["80.00", "20.00", "5.00"],
        "rap_inscritos": "0", "rap_cancelados": "0", "rap_pagos": "0"}))
    w(d / "emendas" / "pagamentos" / "2024.csv", pd.DataFrame({
        "codigo_emenda": ["E1", "E1", "E2", "E3"], "ano_mes": ["2024-05", "2024-06", "2024-07", "2024-07"], "favorecido": "", "tipo_favorecido": "x",
        "uf": ["SP", "SP", "DF", "SP"], "municipio": ["EMBU", "SAO PAULO", "BRASILIA", "EMBU"], "n_favorecidos": "1", "valor": ["50.00", "30.00", "20.00", "5.00"]}))
    w(d / "siconfi" / "entes.csv", pd.DataFrame({"cod_ibge": ["3515004", "3550308"], "ente": ["Embu das Artes", "São Paulo"], "uf": "SP", "regiao": "SE",
                                                 "populacao": ["250000", "11000000"], "cnpj": "x", "capital": ["0", "1"]}))
    w(d / "ref" / "prefeitos.csv", pd.DataFrame({
        "ano": "2020", "cod_ibge": ["3515004", "3550308"], "municipio": "x", "uf": "SP", "sg_ue": "1", "eleicao": "x", "data_eleicao": "2020-11-15",
        "suplementar": "0", "turno": "1", "sq_candidato": ["m1", "m2"], "nome_urna": ["A", "B"], "partido": ["P1", "MDB"], "genero": "x", "cor_raca": "x"}))
    w(d / "tse" / "2022" / "doacoes_grandes_doadores.csv", pd.DataFrame({"doador": ["***.111.111-**"], "nome": ["ANA"], "sq_candidato": ["s10"], "valor": ["60000.00"]}))
    w(d / "site" / "sancoes" / "autores.csv", pd.DataFrame({"autor_codigo": ["900"], "autor": "x", "kind": "deputado", "pessoa": ["camara:10"], "partido": "P1", "uf": "SP",
                                                           "primeiro": "2024", "ultimo": "2024", "emendas": "2", "pago_total": ["100.00"], "pago_sancionadas": ["10.00"],
                                                           "pago_sim": "0", "share": "0.1", "empresas_sancionadas": ["1"]}))
    return d


def test_build(tmp_path, monkeypatch):
    d = fixture(tmp_path)
    monkeypatch.setattr(sd, "MIN_SHARED", 1)   # the fixture has three contested roll calls
    r = sd.build(d)
    graphs._load.cache_clear()
    out = d / "site" / "deputados"
    assert r[57]["deputies"] == 4

    em = pd.read_csv(out / "emendas_57.csv", dtype=str).set_index("tipo")
    assert em.loc["individual", "pago"] == "80.0" and em.loc["especial", "pago"] == "20.0"   # E3 is no deputy's

    de = pd.read_csv(out / "destinos_57.csv", dtype=str, keep_default_na=False)
    assert de[["uf", "municipio_ibge", "pago"]].values.tolist() == [["SP", "3515004", "50.0"], ["SP", "3550308", "30.0"], ["DF", "", "20.0"]]

    v = pd.read_csv(out / "deputados_57.csv", dtype={"deputado_id": str}).set_index("deputado_id")
    ten = v.loc["10"]
    assert (ten.emendas_pago_estado, ten.emendas_pago_nacional) == (0.8, 0.2)
    assert (ten.grandes_doadores, ten.grandes_doadores_valor) == (1, 60000)
    assert (ten.sancoes_pago_sancionadas, ten.sancoes_empresas) == (10, 1)
    # Embu's mayor is P1, as is deputy 10; São Paulo's is MDB. Half of SP's towns are P1's.
    assert (ten.prefeito_mesmo_partido, ten.prefeito_base) == (0.625, 0.5)
    assert np.isnan(v.loc["20", "prefeito_mesmo_partido"])

    nb = pd.read_csv(out / "vizinhos_57.csv", dtype=str)
    ten_nb = nb[nb.deputado_id == "10"]
    # 10 and 20 voted alike on v1 and v2 and apart on v5; 30 and 40 voted against 10 on both v1 and v2.
    assert ten_nb[ten_nb.tipo == "perto"].outro_id.iloc[0] == "20"
    assert ten_nb[ten_nb.tipo == "perto"].concordancia.iloc[0] == "0.6667"
    assert ten_nb[ten_nb.tipo == "longe"].outro_id.tolist()[:2] == ["30", "40"]
    assert pd.read_csv(out / "legislaturas.csv").legislatura.tolist() == [57]


def test_party_in_follows_mergers():
    assert sd.party_in("DEM", 2021) == "DEM" and sd.party_in("DEM", 2022) == "UNIÃO" == sd.party_in("UNIÃO", 2022)
    assert sd.party_in("PC do B", 2020) == sd.party_in("PCdoB", 2020) == "PCDOB"
    assert sd.party_in("REPUBLIC", 2024) == "REPUBLICANOS" == sd.party_in("PRB", 2016)
    assert sd.party_in("PTB", 2023) == "PTB" and sd.party_in("PTB", 2024) == "PRD"


def test_wilson_prefers_the_longer_record():
    lo_short, _ = sd.wilson(np.array(50.0), np.array(52.0))
    lo_long, _ = sd.wilson(np.array(480.0), np.array(500.0))
    assert lo_long > lo_short
