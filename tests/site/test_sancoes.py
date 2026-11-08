"""The sanctions page's summaries, on a tiny world: one barred company paid by one deputy's amendment."""

import json

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import sancoes as s

CEIS_COLS = ["cadastro", "codigo_da_sancao", "tipo_de_pessoa", "cpf_ou_cnpj_do_sancionado", "nome_do_sancionado",
             "nome_informado_pelo_orgao_sancionador", "razao_social_cadastro_receita", "nome_fantasia_cadastro_receita",
             "numero_do_processo", "categoria_da_sancao", "data_inicio_sancao", "data_final_sancao", "data_publicacao",
             "publicacao", "detalhamento_do_meio_de_publicacao", "data_do_transito_em_julgado", "abragencia_da_sancao",
             "orgao_sancionador", "uf_orgao_sancionador", "esfera_orgao_sancionador", "fundamentacao_legal",
             "data_origem_informacao", "origem_informacoes", "observacoes"]
CO, OTHER, PERSON = "11111111000111", "22222222000122", "***.462.240-**"


def sanction(code, tipo, doc, name, cat, start, end, scope, sphere, uf="RJ", law="g1"):
    r = dict.fromkeys(CEIS_COLS, "")
    r.update(cadastro="CEIS", codigo_da_sancao=code, tipo_de_pessoa=tipo, cpf_ou_cnpj_do_sancionado=doc,
             nome_do_sancionado=name, razao_social_cadastro_receita=name if tipo == "J" else "", categoria_da_sancao=cat,
             data_inicio_sancao=start, data_final_sancao=end, abragencia_da_sancao=scope, orgao_sancionador="Fundo X",
             uf_orgao_sancionador=uf, esfera_orgao_sancionador=sphere, fundamentacao_legal=law,
             data_origem_informacao=start, origem_informacoes="CGU")
    return r


def world(tmp_path):
    d = tmp_path / "data"
    sc = d / "sancoes"
    ceis = pd.DataFrame([
        sanction("1", "J", CO, "BARRED LTDA", "Declaração de Inidoneidade sem prazo determinado", "2025-11-18", "",
                 "Todas as Esferas em todos os Poderes", "MUNICIPAL"),
        sanction("2", "J", OTHER, "LOCAL LTDA", "Suspensão", "2025-01-01", "2026-12-31", "No órgão sancionador", "MUNICIPAL"),
        sanction("3", "F", PERSON, "FULANO DE TAL", "Impedimento/proibição de contratar com prazo determinado",
                 "2024-01-01", "2026-11-20", "Sem Informação", "ESTADUAL"),
    ])
    write_csv(ceis, sc / "ceis.csv")
    cnep = ceis.iloc[:0].assign(valor_da_multa=[])
    write_csv(cnep, sc / "cnep.csv")
    write_csv(pd.DataFrame(columns=["cnpj_entidade", "nome_entidade", "numero_convenio", "orgao_concedente", "motivo_do_impedimento"]), sc / "cepim.csv")
    write_csv(pd.DataFrame([{"id_do_acordo": "9", "cnpj_do_sancionado": "33333333000133", "razao_social_cadastro_receita": "BIG SA",
                             "nome_fantasia_cadastro_receita": "", "data_de_inicio_do_acordo": "2019-05-31", "data_de_fim_do_acordo": "",
                             "situacao_do_acordo_de_lenienica": "Cumprido", "data_da_informacao": "", "numero_do_processo": "",
                             "termos_do_acordo": "as empresas do grupo OAS, definindo o pagamento no valor total de R$ 1.929.257.982,37, "
                                                 "dos quais R$ 320.067.086,02 correspondem a multa", "orgao_sancionador": "CGU"}]), sc / "leniencia.csv")
    write_csv(pd.DataFrame([{"id_do_acordo": "9", "efeito_do_acordo_de_leniencia": "Outros", "complemento": ""}]), sc / "leniencia_efeitos.csv")
    write_csv(pd.DataFrame(columns=["data", "lista", "codigo", "mudanca", "tipo_de_pessoa", "documento", "nome"]), sc / "changes.csv")
    write_csv(pd.DataFrame([{"id": "g1", "texto": "LEI 14133 - ART. 156, IV - DECLARAÇÃO"}]), sc / "ref" / "fundamentacoes.csv")
    (sc / "sources.json").write_text(json.dumps({"ceis": {"date": "2026-11-06"}, "cepim": {"date": "2026-10-28"}}))
    # One deputy's amendment pays the barred company before and after its sanction, and another company.
    write_csv(pd.DataFrame([
        {"codigo": "202600010001", "ano": "2026", "tipo": "individual", "autor_codigo": "10", "autor": "DEP UM"},
        {"codigo": "202500020001", "ano": "2025", "tipo": "bancada", "autor_codigo": "7102", "autor": "BANCADA DO ACRE"},
    ]), d / "emendas" / "emendas" / "2026.csv")
    write_csv(pd.DataFrame([
        {"codigo_emenda": "202600010001", "ano_mes": "2025-10", "favorecido": CO, "tipo_favorecido": "Pessoa Jurídica", "uf": "RJ", "municipio": "", "n_favorecidos": "1", "valor": "100.00"},
        {"codigo_emenda": "202600010001", "ano_mes": "2026-03", "favorecido": CO, "tipo_favorecido": "Pessoa Jurídica", "uf": "RJ", "municipio": "", "n_favorecidos": "1", "valor": "300.00"},
        {"codigo_emenda": "202600010001", "ano_mes": "2026-03", "favorecido": OTHER, "tipo_favorecido": "Pessoa Jurídica", "uf": "RJ", "municipio": "", "n_favorecidos": "1", "valor": "50.00"},
        {"codigo_emenda": "202600010001", "ano_mes": "2026-03", "favorecido": "3304557", "tipo_favorecido": "Pessoa Jurídica", "uf": "RJ", "municipio": "", "n_favorecidos": "1", "valor": "550.00"},
        {"codigo_emenda": "202500020001", "ano_mes": "2026-04", "favorecido": CO, "tipo_favorecido": "Pessoa Jurídica", "uf": "RJ", "municipio": "", "n_favorecidos": "1", "valor": "10.00"},
    ]), d / "emendas" / "pagamentos" / "2026.csv")
    write_csv(pd.DataFrame([{"pessoa": "camara:5", "fonte": "camara", "id": "5", "nome": "Dep Um", "metodo": ""},
                            {"pessoa": "camara:5", "fonte": "emendas", "id": "10", "nome": "DEP UM", "metodo": "x"}]), d / "ref" / "politicians.csv")
    write_csv(pd.DataFrame([{"deputado_id": "5", "nome": "Dep Um", "partido": "PXX", "uf": "RJ", "n_votes": "1", "n_authored": "0"}]),
              d / "camara" / "deputies" / "2025-02.csv")
    write_csv(pd.DataFrame([{"cod_ibge": "3304557", "ente": "Rio de Janeiro", "uf": "RJ", "regiao": "SE", "populacao": "1000000", "cnpj": "", "capital": "1"}]),
              d / "siconfi" / "entes.csv")
    write_csv(pd.DataFrame([{"cnpj": CO, "nome": "BARRED LTDA", "cnae": "", "total": "70.00", "n_candidatos": "2"}]), d / "tse" / "2026" / "fornecedores.csv")
    return d


def test_amounts():
    assert s.amounts("valor total de R$ 2.872.038.787,73, dos quais R$ 126.501.512,33 correspondem a multa") == (2872038787.73, "BRL", 126501512.33)
    assert s.amounts("pagamento no valor total de 2.658.169,73 EUROS, dos quais 355.235,62 EUROS correspondem a multa") == (2658169.73, "EUR", 355235.62)
    assert s.amounts("sem valor") == (None, "", None)


def test_in_force_by_day_and_month():
    start, end = pd.Series(["2025-11-18", "2025-01-01", ""]), pd.Series(["", "2025-03-10", ""])
    assert s.in_force(start, end, "2026-01-01").tolist() == [True, False, False]
    assert s.in_force(start, end, "2025-11", month=True).tolist() == [True, False, False]   # any overlap with the month
    assert s.in_force(start, end, "2025-03", month=True).tolist() == [False, True, False]


def test_federal_scope():
    t = pd.DataFrame({"abrangencia": ["Todas as Esferas em todos os Poderes", "Em todos os Poderes da Esfera do órgão sancionador",
                                      "No órgão sancionador", "Em todos os Poderes da Esfera do órgão sancionador"],
                      "esfera": ["MUNICIPAL", "FEDERAL", "FEDERAL", "ESTADUAL"]})
    assert s.federal_scope(t).tolist() == ["sim", "sim", "possivel", "nao"]


def test_party_at_takes_the_latest_month_before_else_the_first_after():
    tl = pd.DataFrame({"pessoa": ["a", "a"], "month": ["2019-02", "2023-02"], "casa": "camara", "partido": ["P1", "P2"], "uf": "SP"})
    keys = pd.DataFrame({"pessoa": ["a", "a", "a", "b"], "month": ["2018-07", "2021-07", "2024-07", "2021-07"]}, index=[10, 11, 12, 13])
    got = s.party_at(keys, tl)
    assert got.partido.tolist() == ["P1", "P1", "P2", ""] and got.index.tolist() == [10, 11, 12, 13]


def test_build(tmp_path):
    d = world(tmp_path)
    s.build(d)
    out = d / "site" / "sancoes"
    r = json.loads((out / "resumo.json").read_text())
    assert r["tiles"]["empresas"] == 2 and r["tiles"]["pessoas"] == 1 and r["tiles"]["vigentes"] == 3
    # Paid while barred: only the March 2026 payments (the October 2025 one came before the sanction).
    e = r["money"]["emendas"]
    assert e["barrado"] == 360.0 and e["barrado_sim"] == 310.0 and e["total"] == 460.0
    idx = pd.read_csv(out / "empresas.csv", dtype={"cnpj": str}).set_index("cnpj")
    assert idx.loc[CO, "emendas"] == 410.0 and idx.loc[CO, "emendas_sancionada"] == 310.0 and idx.loc[CO, "campanhas"] == 70.0
    # The deputy's party in the amendment's year, and their share of everything their amendment paid (1000).
    au = pd.read_csv(out / "autores.csv", dtype={"autor_codigo": str}).set_index("autor_codigo")
    assert au.loc["10", "partido"] == "PXX" and au.loc["10", "kind"] == "deputado"
    assert au.loc["10", "pago_total"] == 1000.0 and au.loc["10", "pago_sancionadas"] == 350.0 and au.loc["10", "pago_sim"] == 300.0
    assert au.loc["7102", "kind"] == "bancada"
    pt = pd.read_csv(out / "partidos.csv").set_index("partido")
    assert abs(pt.loc["PXX", "share"] - 0.35) < 1e-9
    shard = json.loads((out / "empresas" / "11.json").read_text())[CO]
    assert shard["a"][0][:2] == ["DEP UM", "PXX"] and len(shard["s"]) == 1
    le = pd.read_csv(out / "leniencia.csv")
    assert le.nome[0] == "OAS group" and le.valor_total[0] == 1929257982.37
    # People are counted, never named or listed.
    for p in out.rglob("*"):
        if p.is_file():
            text = p.read_text()
            assert "FULANO" not in text and PERSON not in text, p.name


def test_build_is_deterministic(tmp_path):
    d = world(tmp_path)
    s.build(d)
    first = {p: p.read_bytes() for p in (d / "site").rglob("*") if p.is_file()}
    s.build(d)
    assert first == {p: p.read_bytes() for p in (d / "site").rglob("*") if p.is_file()}
