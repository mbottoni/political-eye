"""A tiny amendments zip in the real format: latin-1, ';', every field quoted, CRLF."""

import csv
import io
import zipfile

import pandas as pd
import pytest

from politicaleye.emendas import build as b

EM = ["Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda",
      "Número da emenda", "Localidade de aplicação do recurso", "Código Município IBGE", "Município", "Código UF IBGE",
      "UF", "Região", "Código Função", "Nome Função", "Código Subfunção", "Nome Subfunção", "Código Programa",
      "Nome Programa", "Código Ação", "Nome Ação", "Código Plano Orçamentário", "Nome Plano Orçamentário",
      "Valor Empenhado", "Valor Liquidado", "Valor Pago", "Valor Restos A Pagar Inscritos",
      "Valor Restos A Pagar Cancelados", "Valor Restos A Pagar Pagos"]
FAV = ["Código da Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda", "Número da emenda", "Tipo de Emenda",
       "Ano/Mês", "Código do Favorecido", "Favorecido", "Natureza Jurídica", "Tipo Favorecido", "UF Favorecido",
       "Município Favorecido", "Valor Recebido"]
CONV = ["Código da Emenda", "Código Função", "Nome Função", "Código Subfunção", "Nome Subfunção", "Localidade do gasto",
        "Tipo de Emenda", "Data Publicação Convênio", "Convenente", "Objeto Convênio", "Número Convênio", "Valor Convênio"]

IND, PIX = "Emenda Individual - Transferências com Finalidade Definida", "Emenda Individual - Transferências Especiais"


def em(code, ano, tipo, autor, ibge, loc, emp, pago, acao="2E90"):
    return [code, ano, tipo, autor[0], autor[1], code[-4:] if code != "Sem informação" else "S/I", loc, ibge,
            "PARNAÍBA", "2200000", "PIAUÍ", "Nordeste", "10", "Saúde", "302", "Assistência hospitalar", "5118",
            "ATENÇÃO ESPECIALIZADA", acao, "APOIO", "0000", "APOIO - DESPESAS", emp, "0,00", pago, "0,00", "0,00", "0,00"]


def fav(code, am, who, name, nat, tipo, valor, uf="PI", mun="PARNAÍBA"):
    return [code, "1246", "JULIO CESAR", code[-4:], IND, am, who, name, nat, tipo, uf, mun, valor]


def table(header, rows) -> bytes:
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return s.getvalue().encode("latin1")


@pytest.fixture
def zip_path(tmp_path):
    p = tmp_path / "EmendasParlamentares.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("EmendasParlamentares.csv", table(EM, [
            em("202512460001", "2025", IND, ("1246", "JULIO CESAR"), "2207702", "PARNAÍBA - PI", "3000000,00", "2500000,50"),
            em("202512460002", "2025", PIX, ("1246", "JULIO CESAR"), "2207702", "PARNAÍBA - PI", "1.000,10", "1.000,10"),
            em("202412460001", "2024", IND, ("1246", "JULIO CESAR"), "", "MÚLTIPLO", "10,00", "0,00"),
            em("Sem informação", "2014", IND, ("S/I", "Sem informação"), "2207702", "PARNAÍBA - PI", "-5,00", "0,00"),
        ]))
        z.writestr("EmendasParlamentares_PorFavorecido.csv", table(FAV, [
            fav("202512460001", "202503", "07523186000102", "HOSPITAL X LTDA", "Sociedade Empresária Limitada",
                "Pessoa Jurídica", "100,00"),
            fav("202512460001", "202503", "07523186000102", "HOSPITAL X", "Sociedade Empresária Limitada",
                "Pessoa Jurídica", "50,00"),
            fav("202512460001", "202504", "07523186000102", "HOSPITAL X LTDA", "Sociedade Empresária Limitada",
                "Pessoa Jurídica", "25,00"),
            fav("202512460001", "202503", "***.548.092-**", "MARIA DA SILVA", "Sem informação", "Pessoa Fisica", "10,00"),
            fav("202512460001", "202503", "***.128.702-**", "JOSE SOUZA", "Sem informação", "Pessoa Fisica", "20,00"),
            fav("202512460001", "202503", "12345678901", "ANA LIMA", "Sem informação", "Sem informação", "5,00"),
            fav("202512460001", "202503", "EXVINICIU", "VINICIUS COSTA", "Sem informação", "Inscrição Genérica", "7,00"),
            fav("202512460001", "202503", "170500", "FUNDO NACIONAL", "Órgão Público", "Unidade Gestora", "1,00"),
            fav("202512460001", "202503", "RB0000104", "CAIXA ECONOMICA FEDERAL - AG.OPERADORA PBF", "Sem informação",
                "Inscrição Genérica", "9,00"),
            fav("202512460001", "202503", "EX2544357", "QIAGEN GMBH", "Sem informação", "Inscrição Genéric", "3,00"),
        ]))
        z.writestr("EmendasParlamentares_Convenios.csv", table(CONV, [
            ["202512460001", "10", "Saúde", "302", "Assistência", "PIAUÍ (UF)", IND, "19/12/2025", "INSTITUTO Y",
             "Aquisição de\r\n equipamento", "984424", "200000,00"],
        ]))
    return p


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def test_money():
    s = pd.Series(["3000000,00", "1.000,10", "-5,00", "", "0,5", ",25"])
    c = b.cents(s)
    assert c.tolist() == [300000000, 100010, -500, 0, 50, 25]
    assert b.reais(c).tolist() == ["3000000.00", "1000.10", "-5.00", "0.00", "0.50", "0.25"]


def test_emendas(zip_path, tmp_path):
    data = tmp_path / "data"
    r = b.build(zip_path, data)
    e = read(data / "emendas" / "2025.csv")
    assert e.columns.tolist() == b.EMENDAS
    assert e.tipo.tolist() == ["individual", "especial"]
    assert e[["empenhado", "pago"]].values.tolist() == [["3000000.00", "2500000.50"], ["1000.10", "1000.10"]]
    old = read(data / "emendas" / "2014.csv").iloc[0]
    assert (old.codigo, old.autor_codigo, old.autor, old.numero, old.empenhado) == ("", "", "", "", "-5.00")
    assert r["emendas_without_code"] == 1 and r["tipos_unmapped"] == 0
    assert read(data / "ref" / "acoes.csv").values.tolist() == [["2E90", "APOIO"]]
    assert read(data / "ref" / "municipios.csv").municipio_ibge.tolist() == ["2207702"]


def test_private_individuals_are_never_named(zip_path, tmp_path):
    data = tmp_path / "data"
    r = b.build(zip_path, data)
    p = read(data / "pagamentos" / "2025.csv")
    assert p.columns.tolist() == b.PAGAMENTOS
    named = p[p.favorecido != ""]
    assert named.favorecido.tolist() == ["07523186000102", "07523186000102", "170500", "EX2544357", "RB0000104",
                                         "07523186000102"]
    summed = p[p.favorecido == ""].set_index("tipo_favorecido")
    assert summed.loc["Pessoa Fisica", ["n_favorecidos", "valor"]].tolist() == ["2", "30.00"]
    assert summed.loc["Sem informação", "valor"] == "5.00"          # an 11-digit code: maybe a CPF
    assert summed.loc["Inscrição Genérica", "valor"] == "7.00"      # generic codes can hide a person
    text = "".join(p.read_text(encoding="utf-8") for p in data.rglob("*.csv"))
    for secret in ("MARIA", "JOSE", "ANA LIMA", "VINICIUS", "548.092", "12345678901", "EXVINICIU"):
        assert secret not in text
    assert r["pagamentos_named"] == 6 and r["pagamentos_summed"] == 4


def test_favorecidos_one_name_each(zip_path, tmp_path):
    data = tmp_path / "data"
    b.build(zip_path, data)
    f = read(data / "favorecidos.csv").set_index("favorecido")
    assert f.loc["07523186000102", "nome"] == "HOSPITAL X LTDA"     # the most frequent
    assert f.loc["170500", "tipo"] == "Unidade Gestora"


def test_convenios_and_totals(zip_path, tmp_path):
    data = tmp_path / "data"
    b.build(zip_path, data)
    c = read(data / "convenios" / "2025.csv").iloc[0]
    assert (c.data_publicacao, c.objeto, c.valor) == ("2025-12-19", "Aquisição de equipamento", "200000.00")
    a = read(data / "por_autor.csv")
    row = a[(a.autor_codigo == "1246") & (a.ano == "2025") & (a.tipo == "individual")].iloc[0]
    assert (row.emendas, row.empenhado, row.pago) == ("1", "3000000.00", "2500000.50")
    m = read(data / "por_municipio.csv")
    assert m[m.ano == "2025"][["tipo", "pago"]].values.tolist() == [["especial", "1000.10"], ["individual", "2500000.50"]]


def test_rebuild_is_byte_identical(zip_path, tmp_path):
    data = tmp_path / "data"
    b.build(zip_path, data)
    before = {p: p.read_bytes() for p in data.rglob("*.csv")}
    (data / "emendas" / "1999.csv").write_text("stale\n")
    b.build(zip_path, data)
    assert {p: p.read_bytes() for p in data.rglob("*.csv")} == before
