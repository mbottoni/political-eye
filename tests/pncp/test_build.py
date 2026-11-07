import datetime as dt

import pandas as pd

from politicaleye.pncp import build as b


def rec(ctrl, valor, ni="34766442000165", kind="PJ", nome="WM LTDA", signed="2026-11-04", pub="2026-11-05T10:00:00",
        esfera="M", objeto="Piso vinílico"):
    return {"numeroControlePNCP": ctrl, "numeroControlePncpCompra": "c", "dataPublicacaoPncp": pub,
            "dataAssinatura": signed, "dataVigenciaInicio": signed, "dataVigenciaFim": "2027-11-04",
            "orgaoEntidade": {"cnpj": "11583495000145", "razaoSocial": "FUNDO MUNICIPAL DE SAUDE DE CACADOR", "esferaId": esfera,
                              "poderId": "E"},
            "unidadeOrgao": {"ufSigla": "SC", "codigoIbge": "4203006"}, "tipoContrato": {"nome": "Contrato (termo inicial)"},
            "categoriaProcesso": {"nome": "Serviços"}, "tipoPessoa": kind, "niFornecedor": ni,
            "nomeRazaoSocialFornecedor": nome, "objetoContrato": objeto, "valorInicial": valor, "valorGlobal": valor,
            "numeroRetificacao": 0}


def sancoes(root):
    s = root / "sancoes"
    s.mkdir(parents=True)
    pd.DataFrame({"codigo_da_sancao": ["1", "2", "3"],
                  "cpf_ou_cnpj_do_sancionado": ["34766442000165", "***.462.240-**", "34766442000165"],
                  "categoria_da_sancao": ["Suspensão", "Suspensão", "Multa"],
                  "data_inicio_sancao": ["2026-01-01", "2026-01-01", "2026-01-01"], "data_final_sancao": ["2026-12-31", "", ""],
                  "abragencia_da_sancao": ["No órgão sancionador"] * 3, "orgao_sancionador": ["Prefeitura de Caçador"] * 3,
                  "esfera_orgao_sancionador": ["MUNICIPAL"] * 3, "uf_orgao_sancionador": ["SC"] * 3,
                  }).to_csv(s / "ceis.csv", index=False)


def test_tidy_masks_people():
    t = b.tidy(rec("x", 10.5, ni="86246224091", kind="PF", nome="JOSE SILVA 86246224091",
                   objeto="Serviços de JOSE, CPF 018.714.277-70, " + "a" * 300))
    assert t["fornecedor"] == "***.462.240-**" and t["fornecedor_nome"] == "JOSE SILVA ***.462.240-**"
    assert "018.714.277-70" not in t["objeto"] and len(t["objeto"]) == b.OBJETO_MAX
    assert t["valor_global"] == "10.50" and t["publicacao"] == "2026-11-05"


def test_update(monkeypatch, tmp_path):
    sancoes(tmp_path)
    pub = {"2026-11-06": [rec("a", 2_000_000), rec("b", 999.99, ni="11111111000111"),
                          rec("c", 50, signed="2025-12-31")],                    # signed before the sanction
           "2026-11-05": [rec("d", 1_000_000, ni="22222222000122", esfera="F", pub="2026-11-05T09:00:00")]}
    upd = {"2026-11-07": [rec("d", 10, ni="22222222000122", pub="2026-11-05T09:00:00")]}   # d revised down later

    def contratos(day, updated=False):
        return (upd if updated else pub).get(day, [])
    monkeypatch.setattr(b.fetch, "contratos", contratos)
    data = tmp_path / "pncp"
    r = b.update(data, today=dt.date(2026, 11, 7), days=2)
    assert r["dias"] == 2 and r["atualizados"] == 0
    big = pd.read_csv(data / "contratos" / "2026-11.csv", dtype=str)
    assert big.controle.tolist() == ["a", "d"]                                    # by publication day, then id
    s = pd.read_csv(data / "contratos_sancionados.csv", dtype=str)
    assert s.controle.tolist() == ["a"] and s.lista.tolist() == ["ceis"]          # c was signed before it; a fine bars nothing
    assert s.cobre.tolist() == ["possivel"]                                       # same sphere and state
    res = pd.read_csv(data / "resumo_dia.csv", dtype=str)
    assert res.values.tolist() == [["2026-11-05", "F", "PJ", "1", "1000000.00"], ["2026-11-06", "M", "PJ", "3", "2001049.99"]]
    dias = pd.read_csv(data / "dias.csv", dtype=str, keep_default_na=False)
    assert dias.values.tolist() == [["2026-11-05", "1", ""], ["2026-11-06", "3", "0"]]

    r = b.update(data, today=dt.date(2026, 11, 8), days=1)                        # the next day
    assert r["atualizados"] == 1 and r["dias"] == 1
    big = pd.read_csv(data / "contratos" / "2026-11.csv", dtype=str)
    assert big.controle.tolist() == ["a"]                                         # d fell below the threshold
    assert pd.read_csv(data / "dias.csv", dtype=str).dia.tolist() == ["2026-11-05", "2026-11-06", "2026-11-07"]


def test_covers():
    m = pd.DataFrame({
        "abrangencia": ["Todas as Esferas em todos os Poderes", "No órgão sancionador",
                        "Em todos os Poderes da Esfera do órgão sancionador", "No órgão sancionador",
                        "Em todos os Poderes da Esfera do órgão sancionador", "Em todos os Poderes da Esfera do órgão sancionador",
                        "No órgão sancionador"],
        "esfera_sancionador": ["MUNICIPAL", "MUNICIPAL", "ESTADUAL", "FEDERAL", "FEDERAL", "MUNICIPAL", "MUNICIPAL"],
        "uf_sancionador": ["SP", "SP", "RJ", "", "", "PR", "PE"],
        "orgao_sancionador": ["X", "X", "Y", "BANCO DO BRASIL S/A", "CGU", "PREFEITURA DE UNIFLOR - PR",
                              "Fundo Municipal de Saúde do Município de Toritama - PE"],
        "esfera": ["F", "F", "E", "F", "F", "M", "M"], "uf": ["SC", "SP", "SP", "DF", "DF", "PR", "PE"],
        "orgao": ["A", "A", "B", "MINISTERIO DA JUSTICA", "MINISTERIO DA SAUDE", "MUNICIPIO DA LAPA", "MUNICIPIO DE TORITAMA"]})
    assert b.covers(m).tolist() == ["sim", "nao", "nao", "nao", "sim", "nao", "possivel"]
