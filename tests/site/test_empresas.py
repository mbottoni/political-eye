"""The company profiles on a tiny world: a barred company across every source, a person's firm, a town, a past sanction."""

import json

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import empresas as e

from .test_sancoes import CEIS_COLS, sanction

CO, PERSON_FIRM, TOWN, OLD, NEW, CAMPAIGN_ONLY = "11111111000111", "22222222000122", "33333333000133", "44444444000144", "55555555000155", "66666666000166"
PERSON = "***.462.240-**"
CONTRACT_COLS = ["controle", "compra", "publicacao", "assinatura", "vigencia_inicio", "vigencia_fim", "orgao_cnpj", "orgao", "esfera", "poder", "uf",
                 "municipio_ibge", "tipo", "categoria", "fornecedor_tipo", "fornecedor", "fornecedor_nome", "objeto", "valor_inicial", "valor_global", "retificacao"]


def contract(controle, fornecedor, nome, objeto, valor, inicial=None, day="2026-03-10"):
    r = dict.fromkeys(CONTRACT_COLS, "")
    r.update(controle=controle, publicacao=day, assinatura=day, orgao_cnpj=controle[:14], orgao="SECRETARIA DE OBRAS", esfera="E", uf="SP",
             fornecedor_tipo="PJ", fornecedor=fornecedor, fornecedor_nome=nome, objeto=objeto, valor_inicial=inicial or valor, valor_global=valor)
    return r


def world(tmp_path, legacy=False):
    d = tmp_path / "data"
    sc = d / "sancoes"
    ceis = pd.DataFrame([
        sanction("1", "J", CO, "BARRED LTDA", "Declaração de Inidoneidade sem prazo determinado", "2025-11-18", "", "Todas as Esferas em todos os Poderes", "FEDERAL"),
        sanction("2", "J", CO, "BARRED LTDA", "Multa", "2020-01-01", "2021-01-01", "Sem Informação", "MUNICIPAL"),
        sanction("3", "F", PERSON, "FULANO DE TAL", "Impedimento/proibição de contratar com prazo determinado", "2024-01-01", "2027-11-20", "Sem Informação", "ESTADUAL"),
    ])
    write_csv(ceis, sc / "ceis.csv")
    write_csv(ceis.iloc[:0].assign(valor_da_multa=[]), sc / "cnep.csv")
    write_csv(pd.DataFrame(columns=["cnpj_entidade", "nome_entidade", "numero_convenio", "orgao_concedente", "motivo_do_impedimento"]), sc / "cepim.csv")
    write_csv(pd.DataFrame(columns=["id_do_acordo", "cnpj_do_sancionado", "razao_social_cadastro_receita", "data_de_inicio_do_acordo", "data_de_fim_do_acordo",
                                    "situacao_do_acordo_de_lenienica", "orgao_sancionador", "termos_do_acordo"]), sc / "leniencia.csv")
    # A company whose sanction left the list, and a person who did: the person is never shown.
    write_csv(pd.DataFrame([{"data": "2026-11-09", "lista": "ceis", "codigo": "77", "mudanca": "saiu", "tipo_de_pessoa": "J", "documento": OLD, "nome": "OLD LTDA"},
                            {"data": "2026-11-09", "lista": "ceis", "codigo": "78", "mudanca": "saiu", "tipo_de_pessoa": "F", "documento": PERSON, "nome": "FULANO DE TAL"}]),
              sc / "changes.csv")
    (sc / "sources.json").write_text(json.dumps({"ceis": {"date": "2026-11-13"}, "cepim": {"date": "2026-11-12"}}))

    write_csv(pd.DataFrame([{"codigo": "E1", "ano": "2025", "tipo": "individual", "autor_codigo": "10", "autor": "DEP UM"}]), d / "emendas" / "emendas" / "2025.csv")
    write_csv(pd.DataFrame([
        {"codigo_emenda": "E1", "ano_mes": "2025-06", "favorecido": CO, "tipo_favorecido": "Pessoa Jurídica", "uf": "SP", "municipio": "SANTOS", "n_favorecidos": "1", "valor": "100.00"},
        {"codigo_emenda": "E1", "ano_mes": "2026-02", "favorecido": CO, "tipo_favorecido": "Pessoa Jurídica", "uf": "SP", "municipio": "SANTOS", "n_favorecidos": "1", "valor": "300.00"},
        {"codigo_emenda": "", "ano_mes": "2026-02", "favorecido": CO, "tipo_favorecido": "Pessoa Jurídica", "uf": "SP", "municipio": "SANTOS", "n_favorecidos": "1", "valor": "5.00"},
        {"codigo_emenda": "E1", "ano_mes": "2026-02", "favorecido": PERSON_FIRM, "tipo_favorecido": "Pessoa Jurídica", "uf": "SP", "municipio": "SANTOS", "n_favorecidos": "1", "valor": "50.00"},
        {"codigo_emenda": "E1", "ano_mes": "2026-02", "favorecido": TOWN, "tipo_favorecido": "Pessoa Jurídica", "uf": "SP", "municipio": "SANTOS", "n_favorecidos": "1", "valor": "900.00"},
    ]), d / "emendas" / "pagamentos" / "2025.csv")
    write_csv(pd.DataFrame({"favorecido": [CO, PERSON_FIRM, TOWN], "nome": ["BARRED LTDA", "JOAO DA SILVA", "MUNICIPIO DE SANTOS"],
                            "natureza_juridica": ["Sociedade Empresária Limitada", "Empresário (Individual)", "Município"], "tipo": "Pessoa Jurídica"}),
              d / "emendas" / "favorecidos.csv")

    write_csv(pd.DataFrame([
        contract("00000000000100-2-000001/2026", CO, "BARRED LTDA", "CONTRATAÇÃO DE EMPRESA ESPECIALIZADA PARA EXECUÇÃO DE OBRA DE PAVIMENTAÇÃO", "2000000.00"),
        contract("00000000000100-2-000002/2026", CO, "BARRED LTDA", "Obra", "40000000000.00"),   # a typo: left out, counted apart
        contract("00000000000100-2-000003/2026", NEW, "NEW SUPPLIER LTDA", "Aquisição de medicamentos", "1500000.00"),
        contract("00000000000100-2-000004/2026", PERSON_FIRM, "JOAO DA SILVA", "Serviços prestados por JOAO DA SILVA ao município", "1200000.00"),
    ]), d / "pncp" / "contratos" / "2026-03.csv")
    barred = pd.DataFrame([contract("00000000000100-2-000005/2026", CO, "BARRED LTDA", "Pequena compra", "8000.00")]).assign(cobre="sim")
    if legacy:
        write_csv(barred, d / "pncp" / "contratos_sancionados.csv")
    else:
        write_csv(barred, d / "pncp" / "sancionados" / "2026-03.csv")
    write_csv(pd.DataFrame({"dia": ["2026-03-10"], "publicados": ["10"], "atualizados": [""]}), d / "pncp" / "dias.csv")

    write_csv(pd.DataFrame({"cnpj": [CO, CAMPAIGN_ONLY], "nome": ["BARRED LTDA", "GRAFICA X LTDA"], "cnae": ["Construção", "Impressão"],
                            "total": ["70000.00", "90000.00"], "n_candidatos": ["3", "4"]}), d / "tse" / "2022" / "fornecedores.csv")
    write_csv(pd.DataFrame({"sq_candidato": ["s1", "s1"], "cnpj": [CO, CAMPAIGN_ONLY], "valor": ["6000.00", "9000.00"]}), d / "tse" / "2022" / "fornecedores_candidatos.csv")
    write_csv(pd.DataFrame([{"sq_candidato": "s1", "cargo": "Deputado Federal", "uf": "SP", "ue": "SP", "numero": "1", "nome": "ANA LIMA", "nome_urna": "ANA LIMA",
                             "partido": "PA", "federacao": "", "situacao_candidatura": "", "resultado": "ELEITO POR QP", "genero": "", "cor_raca": "", "ocupacao": ""}]),
              d / "tse" / "2022" / "candidatos.csv")

    write_csv(pd.DataFrame({"pessoa": ["camara:1", "camara:1", "camara:1"], "fonte": ["camara", "emendas", "tse"], "id": ["1", "10", "s1"],
                            "nome": ["Ana Lima", "DEP UM", "ANA LIMA"], "metodo": ""}), d / "ref" / "politicians.csv")
    write_csv(pd.DataFrame({"pessoa": ["camara:1"], "deputado_id": ["1"], "nome": ["Ana Lima"], "partido": ["PA"], "uf": ["SP"], "campanha_sq_candidato": ["s1"]}),
              d / "views" / "deputados_57.csv")
    write_csv(pd.DataFrame([{"cnpj": CO, "nome": "BARRED LTDA", "pf": "0", "pessoa": "camara:1", "deputado_id": "1", "senador_id": "", "casa": "camara", "leg": "57",
                             "autor": "Ana Lima", "tipo": "individual", "partido": "PA", "uf": "SP", "barrado": "sim", "valor": "300.0", "pagamentos": "1",
                             "primeiro": "2026-02", "ultimo": "2026-02"}]), d / "site" / "alertas" / "emendas_impedidas.csv")
    return d


def shard(d, cnpj):
    return json.loads((d / "site" / "empresas" / "perfis" / f"{cnpj[:3]}.json").read_text()).get(cnpj)


def test_who_is_in(tmp_path):
    d = world(tmp_path)
    e.build(d)
    ix = pd.read_csv(d / "site" / "empresas" / "indice.csv", dtype=str, keep_default_na=False).set_index("cnpj")
    # The town is a public body; the campaign-only supplier comes in with no other source; the person is never a profile.
    assert sorted(ix.index) == [CO, PERSON_FIRM, OLD, NEW]
    assert ix.fontes[CO] == "SCETA" and ix.fontes[OLD] == "H" and ix.fontes[NEW] == "C" and ix.fontes[PERSON_FIRM] == "CE"


def test_profile_joins_every_source(tmp_path):
    d = world(tmp_path)
    e.build(d)
    r = json.loads((d / "site" / "empresas" / "resumo.json").read_text())
    p = shard(d, CO)
    assert p["n"] == "BARRED LTDA"
    # Sanctions: the bar is in force, the fine ended; categories are positions in resumo.json's list.
    st = {r["categorias"][x[2]]: x[10] for x in p["s"]}
    assert st == {"Declaração de Inidoneidade sem prazo determinado": "v", "Multa": "e"}
    # Contracts: the large one and the small one signed while barred; the typo is left out and counted apart.
    assert p["c"]["n"] == 2 and p["c"]["v"] == 2008000 and p["c"]["x"] == 1 and p["c"]["b"] == [1, 8000]
    assert {x[6]: x[5] for x in p["c"]["t"]}["00000000000100-2-000005/2026"] == "sim"
    assert p["c"]["t"][0][3] == "EXECUÇÃO DE OBRA DE PAVIMENTAÇÃO"   # the boilerplate opening goes
    # Amendments: 405 in all, 305 of them while barred (from November 2025), 5 with no amendment code.
    assert p["e"]["v"] == 405 and p["e"]["u"] == 5 and p["e"]["y"] == [["2025", 100], ["2026", 305, 305]]
    assert p["e"]["a"] == [["10", 400, 300]]
    # Campaigns: every candidate's total, and which federal candidates, linked to the deputy's profile.
    y, total, n, barred, cands, *_ = p["t"][0]
    assert (y, total, n, barred) == ("2022", 70000, 3, 0) and cands[0][:6] == ["Ana Lima", "PA", "SP", "DF", "e", "d57:1"]
    # Red flags, with the member linked.
    assert p["f"]["emendas_impedidas"][:2] == [1, 300] and p["f"]["emendas_impedidas"][2][0][3] == "d57:1"
    assert p["cn"] is not None and r["cnaes"][p["cn"]] == "Construção" and p["lc"] == "SANTOS/SP"
    a = pd.read_csv(d / "site" / "empresas" / "autores.csv", dtype=str, keep_default_na=False)
    assert a.to_dict("records") == [{"autor_codigo": "10", "nome": "Ana Lima", "tipo": "parlamentar", "partido": "PA", "uf": "SP", "link": "d57:1"}]
    assert shard(d, OLD)["h"] == [["2026-11-09", "ceis", "77", "saiu"]]


def test_people_are_never_named(tmp_path):
    d = world(tmp_path)
    e.build(d)
    p = shard(d, PERSON_FIRM)
    assert p["n"] == "" and p["pf"] == 1 and p["e"]["v"] == 50
    assert "JOAO DA SILVA" not in p["c"]["t"][0][3]   # the contract's object named the owner
    for f in (d / "site" / "empresas").rglob("*.*"):
        text = f.read_text()
        for name in ("JOAO DA SILVA", "FULANO DE TAL", "462.240"):
            assert name not in text, (f.name, name)


def test_reads_the_sanctioned_contracts_in_either_layout(tmp_path):
    a = e.sanctioned_contracts(world(tmp_path / "a") / "pncp")
    b = e.sanctioned_contracts(world(tmp_path / "b", legacy=True) / "pncp")
    assert len(a) == len(b) == 1 and a.cobre[0] == b.cobre[0] == "sim"


def test_short_object():
    s = pd.Series(["CONTRATAÇÃO DE EMPRESA ESPECIALIZADA PARA EXECUÇÃO DE OBRA", "[LICITANET] - [LICITANET] - Contratação de empresa para prestação de serviços",
                   "O objeto deste instrumento é a contratação de empresa especializada em limpeza", "REGISTRO DE PREÇOS PARA FUTURA E EVENTUAL AQUISIÇÃO DE PNEUS",
                   "Aquisição de medicamentos", "x" * 100])
    out = e.short_object(s).tolist()
    assert out[:5] == ["EXECUÇÃO DE OBRA", "Prestação de serviços", "Limpeza", "AQUISIÇÃO DE PNEUS", "Aquisição de medicamentos"]
    assert len(out[5]) == e.OBJ and out[5].endswith("…")


def test_whole_and_links():
    assert e.whole({"a": [1234.56, 0.9876, 45.5, "x"]}) == {"a": [1235, 0.9876, 45.5, "x"]}
    link = e.member_link(pd.Series(["1", "2", ""]), pd.Series(["57", "0", "0"]), pd.Series(["", "9", ""]))
    assert link.tolist() == ["d57:1", "s:9", ""]


def test_build_is_deterministic(tmp_path):
    d = world(tmp_path)
    e.build(d)
    first = {p: p.read_bytes() for p in (d / "site" / "empresas").rglob("*") if p.is_file()}
    e.build(d)
    assert first == {p: p.read_bytes() for p in (d / "site" / "empresas").rglob("*") if p.is_file()}
