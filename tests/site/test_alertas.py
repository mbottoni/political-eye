"""The red-flags page's summaries on a tiny world: two deputies, one campaign supplier, one charity, one person's firm."""

import json

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import alertas as a

ASSOC, FIRM, PERSON_FIRM, BANK, POWER = "11111111000111", "22222222000122", "33333333000133", "00000000000191", "44444444000144"


def world(tmp_path):
    d = tmp_path / "data"
    write_csv(pd.DataFrame({"pessoa": ["camara:1", "camara:2"], "deputado_id": ["1", "2"], "nome": ["Ana Lima", "Beto Souza"], "partido": ["PA", "PB"],
                            "uf": ["SP", "RJ"], "campanha_sq_candidato": ["s1", "s2"]}), d / "views" / "deputados_57.csv")
    write_csv(pd.DataFrame({"pessoa": ["camara:1", "camara:1", "camara:2", "camara:2"], "fonte": ["camara", "emendas", "camara", "emendas"],
                            "id": ["1", "901", "2", "902"], "nome": ["Ana Lima", "ANA LIMA", "Beto Souza", "BETO SOUZA"], "metodo": ""}), d / "ref" / "politicians.csv")
    write_csv(pd.DataFrame({"codigo": ["E1", "E2"], "autor_codigo": ["901", "902"]}), d / "emendas" / "emendas" / "2023.csv")
    write_csv(pd.DataFrame([
        # Ana: her campaign's association gets 1.2 M of her 2 M; the bank and the power company are left out.
        {"codigo_emenda": "E1", "ano_mes": "2023-05", "favorecido": ASSOC, "valor": "1200000.00"},
        {"codigo_emenda": "E1", "ano_mes": "2023-06", "favorecido": BANK, "valor": "500000.00"},
        {"codigo_emenda": "E1", "ano_mes": "2023-07", "favorecido": POWER, "valor": "300000.00"},
        # Beto: a person's firm that worked for his campaign gets 20 k of his 10 M.
        {"codigo_emenda": "E2", "ano_mes": "2023-05", "favorecido": PERSON_FIRM, "valor": "20000.00"},
        {"codigo_emenda": "E2", "ano_mes": "2023-05", "favorecido": FIRM, "valor": "9980000.00"},
    ]), d / "emendas" / "pagamentos" / "2023.csv")
    write_csv(pd.DataFrame({"favorecido": [ASSOC, FIRM, PERSON_FIRM, BANK, POWER],
                            "nome": ["ASSOCIACAO CULTURAL X", "MUNICIPIO DE Y", "BETO SOUZA", "BANCO DO BRASIL SA", "COMPANHIA DE ENERGIA Z"],
                            "natureza_juridica": ["Associação Privada", "Município", "Empresário (Individual)", "Sociedade de Economia Mista", "Sociedade Anônima Aberta"],
                            "tipo": "Pessoa Jurídica"}), d / "emendas" / "favorecidos.csv")
    write_csv(pd.DataFrame({"sq_candidato": ["s1", "s1", "s1", "s2"], "cnpj": [ASSOC, BANK, POWER, PERSON_FIRM], "valor": ["300.00", "50.00", "900.00", "5000.00"]}),
              d / "tse" / "2022" / "fornecedores_candidatos.csv")
    write_csv(pd.DataFrame({"sq_candidato": ["s1"], "nome": ["BETO SOUZA"]}), d / "tse" / "2022" / "candidatos.csv")
    return d


def test_kind_and_display():
    assert a.kind_of("FIOTEC - FUNDACAO PARA O DESENVOLVIMENTO CIENTIFICO", "Fundação Privada") == "fundacao_apoio"
    assert a.kind_of("FUNDACAO FACULDADE DE MEDICINA", "Fundação Privada") == "fundacao_apoio"
    assert a.kind_of("SANTA CASA DE MISERICORDIA DA BAHIA", "Associação Privada") == "saude"
    assert a.kind_of("TORRES NOVAS CONSTRUTORA LTDA", "Sociedade Empresária Limitada") == "empresa"
    assert a.kind_of("INSTITUTO BRASIL SOCIAL", "Associação Privada") == "entidade"
    assert a.display("LUIZ CARLOS DA SILVA") == "Luiz Carlos da Silva" and a.display("Ana Lima") == "Ana Lima"
    assert a.UTILITY.search("CEMIG DISTRIBUICAO S.A") and not a.UTILITY.search("UNIAO MUNICIPAL DOS ESTUDANTES")


def test_build(tmp_path):
    d = world(tmp_path)
    a.build(d)
    out = d / "site" / "alertas"
    ce = pd.read_csv(out / "campanha_emendas.csv", dtype=str, keep_default_na=False)
    # Ana's association counts; her bank and power company don't; Beto's own firm counts but is never named.
    assert sorted(ce.cnpj) == [ASSOC, PERSON_FIRM]
    beto = ce[ce.cnpj == PERSON_FIRM].iloc[0]
    assert beto.nome == "" and beto.pf == "1" and beto.deputado == "Beto Souza"
    co = pd.read_csv(out / "concentracao.csv", dtype=str, keep_default_na=False)
    assert co.cnpj.tolist() == [ASSOC] and float(co.share[0]) == 0.6 and co.tipo[0] == "entidade"   # 1.2 M of Ana's 2 M
    r = json.loads((out / "resumo.json").read_text())
    assert r["campanha_emendas"]["casos"] == 2 and r["concentracao"]["casos"] == 1 and r["contratos_impedidas"]["casos"] == 0
    # Nobody's name leaks: no person's firm is named in any table.
    for p in out.glob("*.csv"):
        assert "BETO SOUZA" not in p.read_text(), p.name


def test_build_is_deterministic(tmp_path):
    d = world(tmp_path)
    a.build(d)
    first = {p: p.read_bytes() for p in (d / "site").rglob("*") if p.is_file()}
    a.build(d)
    assert first == {p: p.read_bytes() for p in (d / "site").rglob("*") if p.is_file()}
