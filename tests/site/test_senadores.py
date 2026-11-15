import pandas as pd

from politicaleye.senado import graphs as sg
from politicaleye.site import senadores as ss
from politicaleye.views import senadores as sv
from tests.views.test_senadores import fixture, w


def built(tmp_path, monkeypatch):
    data = fixture(tmp_path)
    # Senator 5 presided v11: that roll call is not one they could vote in.
    p = data / "senado" / "votes" / "2025-03.csv"
    p.write_text(p.read_text().replace("11,5,P-NRV,", "11,5,Presidente (art. 51 RISF),"))
    w(data / "emendas" / "emendas" / "2024.csv", pd.DataFrame({
        "codigo": ["E1", "E2"], "ano": "2024", "tipo": ["especial", "individual"], "autor_codigo": "900", "autor": "ANA", "numero": "1",
        "localidade": "x", "municipio_ibge": "", "uf_ibge": ["3500000", ""], "funcao": "1", "subfuncao": "1", "programa": "1", "acao": "1",
        "plano": "1", "empenhado": ["200.00", "100.00"], "liquidado": "0", "pago": ["100.00", "20.50"], "rap_inscritos": "0",
        "rap_cancelados": "0", "rap_pagos": "0"}))
    w(data / "emendas" / "pagamentos" / "2024.csv", pd.DataFrame({   # a "Pix" amendment, matched by its recipient's town
        "codigo_emenda": ["E1", "E2"], "ano_mes": "2024-05", "favorecido": "", "tipo_favorecido": "x", "uf": ["SP", "DF"],
        "municipio": ["EMBU", "BRASILIA"], "n_favorecidos": "1", "valor": ["100.00", "20.50"]}))
    w(data / "siconfi" / "entes.csv", pd.DataFrame({"cod_ibge": ["3515004"], "ente": ["Embu das Artes"], "uf": "SP", "regiao": "SE",
                                                     "populacao": "1", "cnpj": "x", "capital": "0"}))
    w(data / "tse" / "2022" / "doacoes_grandes_doadores.csv", pd.DataFrame({"doador": ["***.111.111-**"], "nome": ["ANA"],
                                                                           "sq_candidato": ["s22"], "valor": ["60000.00"]}))
    sv.build(57, data)
    monkeypatch.setattr(ss, "MIN_SHARED", 1)   # three contested roll calls in the fixture
    r = ss.build(data)
    sg._load.cache_clear()
    sg._window.cache_clear()
    return data / "site" / "senadores", r


def test_build(tmp_path, monkeypatch):
    out, r = built(tmp_path, monkeypatch)
    assert r[57]["senators"] == 5
    v = pd.read_csv(out / "senadores_57.csv", dtype={"senador_id": str}).set_index("senador_id")
    # Ana: v11, v12, the secret v13 and v16, all voted. Davi was away (AP) for v16. Eva presided v11, voted v12.
    assert (v.loc["1", "presenca"], v.loc["1", "votacoes_mandato"]) == (1.0, 4)
    assert (v.loc["4", "presenca"], v.loc["5", "presenca"], v.loc["5", "presidiu"], v.loc["5", "votacoes_mandato"]) == (0.75, 1.0, 1, 1)
    # Ana signed PL 1 and PEC 4, with others both times; her RQS as PT leader is left out.
    assert (v.loc["1", "propostas_autor"], v.loc["1", "projetos_autor"], v.loc["1", "propostas_coautor"]) == (2, 2, 2)
    assert (v.loc["3", "partidos"], v.loc["1", "partidos"]) == (2, 1)
    assert (v.loc["1", "emendas_pago_estado"], v.loc["1", "emendas_pago_nacional"]) == (0.8299, 0.1701)
    assert (v.loc["1", "grandes_doadores"], v.loc["1", "grandes_doadores_valor"]) == (1, 60000)

    pa = pd.read_csv(out / "partidos_57.csv", dtype=str)
    assert pa[pa.senador_id == "3"][["partido", "de", "ate"]].values.tolist() == [["PL", "2025-03", "2025-03"], ["S.PART.", "2025-04", "2025-04"]]
    k = pd.read_csv(out / "propostas_57.csv", dtype={"senador_id": str}).set_index(["senador_id", "tipo"])
    assert k.loc[("1", "projetos"), "autor"] == 2 and ("1", "requerimentos") not in k.index
    co = pd.read_csv(out / "coautores_57.csv", dtype=str)
    assert co[co.senador_id == "1"].outro_id.tolist() == ["2", "3", "4", "5"]
    de = pd.read_csv(out / "destinos_57.csv", dtype=str, keep_default_na=False)
    assert de[["uf", "municipio_ibge", "pago"]].values.tolist() == [["SP", "3515004", "100.0"], ["DF", "", "20.5"]]

    cp = pd.read_csv(out / "campanhas_57.csv", dtype=str, keep_default_na=False)
    ana = cp[cp.pessoa == "senado:1"].set_index("ano")
    assert ana.loc["2026", ["cargo", "resultado"]].tolist() == ["Senador", "NÃO ELEITO"]
    bia = cp[cp.pessoa == "senado:2"].iloc[0]
    assert (bia.cargo, bia.titular, bia.titular_total) == ("1º Suplente", "TITULAR", "3000.00")   # her slate's senator candidate
    assert ana.loc["2022", "titular"] == ""

    nb = pd.read_csv(out / "vizinhos_57.csv", dtype=str)
    one = nb[nb.senador_id == "1"]
    # Four partners, two each way: Eva voted with Ana on the one vote both cast, Bia on one of two; Caio never did (0 of 3).
    assert one[one.tipo == "perto"].outro_id.tolist() == ["5", "2"] and one[one.tipo == "longe"].outro_id.tolist() == ["3", "4"]
    assert pd.read_csv(out / "legislaturas.csv").legislatura.tolist() == [57]
