import pandas as pd

from politicaleye.site import emendas as se


def w(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def test_build(tmp_path):
    d = tmp_path
    w(d / "emendas" / "emendas" / "2025.csv", pd.DataFrame({
        "codigo": ["1", "2", "3"], "ano": "2025", "tipo": ["individual", "especial", "individual"], "autor_codigo": ["10", "10", "20"],
        "autor": ["ANA", "ANA", "BIA"], "numero": "1", "localidade": "x", "municipio_ibge": ["2211001", "", ""], "uf_ibge": ["2200000", "2200000", ""],
        "funcao": "10", "subfuncao": "1", "programa": "1", "acao": "1", "plano": "1",
        "empenhado": ["100.00", "50.00", "10.00"], "liquidado": "0", "pago": ["80.00", "50.00", "5.00"], "rap_inscritos": "0", "rap_cancelados": "0", "rap_pagos": "0"}))
    w(d / "emendas" / "pagamentos" / "2025.csv", pd.DataFrame({
        "codigo_emenda": ["1", "2", "9"], "ano_mes": ["2025-03", "2025-04", "2025-04"], "favorecido": ["06554869000164", "", ""],
        "tipo_favorecido": ["Pessoa Jurídica", "Pessoa Fisica", "Pessoa Fisica"], "uf": ["PI", "PI", "SP"], "municipio": ["TERESINA", "TERESINA", "EMBU"],
        "n_favorecidos": ["1", "3", "1"], "valor": ["80.00", "50.00", "1.00"]}))
    w(d / "emendas" / "favorecidos.csv", pd.DataFrame({"favorecido": ["06554869000164"], "nome": ["MUNICIPIO DE TERESINA"], "natureza_juridica": ["Município"], "tipo": ["Pessoa Jurídica"]}))
    w(d / "siconfi" / "entes.csv", pd.DataFrame({"cod_ibge": ["2211001", "3515004"], "ente": ["Teresina", "Embu das Artes"], "uf": ["PI", "SP"], "regiao": "x", "populacao": ["900000", "250000"], "cnpj": "x", "capital": "0"}))
    w(d / "ref" / "politicians.csv", pd.DataFrame({"pessoa": ["camara:1", "camara:1"], "fonte": ["camara", "emendas"], "id": ["1", "10"], "nome": ["Ana", "ANA"], "metodo": ["", "x"]}))
    w(d / "camara" / "deputies" / "2025-03.csv", pd.DataFrame({"deputado_id": ["1"], "nome": ["Ana"], "partido": ["Republican"], "uf": ["PI"], "n_votes": [1], "n_authored": [0]}))
    r = se.build(d)
    out = d / "site" / "emendas"
    anos = pd.read_csv(out / "anos.csv", dtype=str).set_index("tipo")
    assert anos.loc["individual", "pago"] == "85.00" and anos.loc["especial", "pago"] == "50.00"
    a = pd.read_csv(out / "autores.csv", dtype=str, keep_default_na=False).set_index("autor_codigo")
    assert a.loc["10", ["partido", "uf", "casa"]].tolist() == ["REPUBLICANOS", "PI", "camara"]   # one key per party
    au = pd.read_csv(out / "autor_uf.csv", dtype=str).iloc[0]
    assert (au.pago, au.pago_estado) == ("130.00", "130.00")                                   # all sent home
    m = pd.read_csv(out / "municipios.csv", dtype=str).set_index("municipio_ibge")
    assert m.loc["2211001", ["valor", "pix"]].tolist() == ["130.00", "50.00"]
    assert m.loc["3515004", "valor"] == "1.00"                                                 # EMBU, renamed since
    assert r["paid_matched_to_a_town"] == 1.0
    top = pd.read_csv(out / "favorecidos.csv", dtype=str)
    assert top.nome.tolist() == ["MUNICIPIO DE TERESINA"]                                     # people are never listed
