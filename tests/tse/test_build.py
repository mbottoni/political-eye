"""Tiny TSE zips in the real layout: latin-1, ';', a *_BRASIL.csv plus per-state copies."""

import csv
import io
import zipfile

import pandas as pd
import pytest

from politicaleye.tse import build as b

CAND = ["NR_TURNO", "SQ_CANDIDATO", "DS_CARGO", "SG_UF", "NM_UE", "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO",
        "NR_CPF_CANDIDATO", "SG_PARTIDO", "SG_FEDERACAO", "DS_SITUACAO_CANDIDATURA", "DS_SIT_TOT_TURNO", "DS_GENERO",
        "DS_COR_RACA", "DS_OCUPACAO"]
REC = ["SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO", "DS_ORIGEM_RECEITA", "DS_FONTE_RECEITA", "DS_NATUREZA_RECEITA",
       "NR_CPF_CNPJ_DOADOR", "NM_DOADOR", "SG_UF_DOADOR", "DS_ESFERA_PARTIDARIA_DOADOR", "SG_PARTIDO_DOADOR", "VR_RECEITA"]
CON = ["SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO", "DS_TIPO_FORNECEDOR", "NR_CPF_CNPJ_FORNECEDOR", "NM_FORNECEDOR",
       "DS_CNAE_FORNECEDOR", "VR_DESPESA_CONTRATADA"]
PAG = ["SQ_PRESTADOR_CONTAS", "VR_PAGTO_DESPESA"]


def table(header, rows) -> bytes:
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return s.getvalue().encode("latin1")


PF, PART = "Recursos de pessoas físicas", "Recursos de partido político"


def rec(cand, origem, fonte, doc, nome, valor, esfera="#NULO", partido="#NULO", uf="SP"):
    return [f"9{cand}", cand, origem, fonte, "FINANCEIRO", doc, nome, uf, esfera, partido, valor]


@pytest.fixture
def raw(tmp_path):
    r = tmp_path / "raw"
    r.mkdir()
    with zipfile.ZipFile(r / "consulta_cand_2026.zip", "w") as z:
        rows = [["1", "1", "DEPUTADO FEDERAL", "SP", "SÃO PAULO", "1301", "ANA SILVA", "ANA", "-4", "PT", "FE BRASIL",
                 "APTO", "ELEITO POR QP", "FEMININO", "PARDA", "PROFESSORA"],
                ["1", "2", "GOVERNADOR", "SP", "SÃO PAULO", "22", "BRUNO LIMA", "BRUNO", "-4", "PL", "#NULO", "APTO",
                 "2º TURNO", "MASCULINO", "BRANCA", "EMPRESÁRIO"],
                ["2", "2", "GOVERNADOR", "SP", "SÃO PAULO", "22", "BRUNO LIMA", "BRUNO", "-4", "PL", "#NULO", "APTO",
                 "ELEITO", "MASCULINO", "BRANCA", "EMPRESÁRIO"]]
        z.writestr("consulta_cand_2026_BRASIL.csv", table(CAND, rows))
        z.writestr("consulta_cand_2026_SP.csv", table(CAND, rows))
    with zipfile.ZipFile(r / "prestacao_de_contas_eleitorais_candidatos_2026.zip", "w") as z:
        z.writestr("receitas_candidatos_2026_BRASIL.csv", table(REC, [
            rec("1", PART, "FUNDO ESPECIAL", "00676213000138", "PT NACIONAL", "500.000,00", "Nacional", "PT", "BR"),
            rec("1", PF, "OUTROS RECURSOS", "86246224091", "CARLOS RICO", "40.000,00"),
            rec("2", PF, "OUTROS RECURSOS", "86246224091", "CARLOS RICO", "20.000,00"),
            rec("1", PF, "OUTROS RECURSOS", "11122233344", "DORA COMUM", "100,00"),
            rec("2", "Recursos próprios", "OUTROS RECURSOS", "-4", "BRUNO LIMA", "1.000,50"),
        ]))
        z.writestr("receitas_candidatos_2026_SP.csv", b"ignored")
        z.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", table(CON, [
            ["91", "1", "PESSOA JURÍDICA", "13347016000117", "FACEBOOK LTDA", "Publicidade", "60.000,00"],
            ["92", "2", "PESSOA FÍSICA", "55566677788", "JOAO CABO", "#NULO", "300,00"],
        ]))
        z.writestr("despesas_pagas_candidatos_2026_BRASIL.csv", table(PAG, [["91", "59.000,00"], ["92", "300,00"]]))
    return r


def read(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def test_candidates_take_the_last_round(raw, tmp_path):
    b.build_year(2026, raw, tmp_path / "d")
    c = read(tmp_path / "d" / "2026" / "candidatos.csv").set_index("sq_candidato")
    assert c.columns.tolist() == b.CANDIDATOS[1:]
    assert c.loc["2", "resultado"] == "ELEITO" and c.loc["2", "federacao"] == ""
    assert c.loc["1", "cargo"] == "Deputado Federal"


def test_money_by_origin_and_fund(raw, tmp_path):
    b.build_year(2026, raw, tmp_path / "d")
    r = read(tmp_path / "d" / "2026" / "receitas_por_candidato.csv").set_index("sq_candidato")
    assert r.loc["1", ["total", "origem_partido", "origem_pessoas_fisicas", "fonte_fefc", "n_doadores_pf"]].tolist() == [
        "540100.00", "500000.00", "40100.00", "500000.00", "2"]
    assert r.loc["2", "origem_proprios"] == "1000.50"
    p = read(tmp_path / "d" / "2026" / "repasses_partidarios.csv")
    assert p.values.tolist() == [["1", "00676213000138", "PT", "Nacional", "BR", "FUNDO ESPECIAL", "500000.00"]]


def test_large_donors_masked_and_thresholded(raw, tmp_path):
    r = b.build_year(2026, raw, tmp_path / "d")
    d = read(tmp_path / "d" / "2026" / "grandes_doadores.csv")
    assert d.values.tolist() == [["***.462.240-**", "CARLOS RICO", "SP", "60000.00", "2"]]   # grouped on the full CPF
    g = read(tmp_path / "d" / "2026" / "doacoes_grandes_doadores.csv")
    assert g[["sq_candidato", "valor"]].values.tolist() == [["1", "40000.00"], ["2", "20000.00"]]
    text = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "d").rglob("*.csv"))
    for secret in ("86246224091", "11122233344", "DORA COMUM", "55566677788", "JOAO CABO"):
        assert secret not in text
    assert r["doadores_pf"] == 2 and r["grandes_doadores"] == 1


def test_expenses(raw, tmp_path):
    b.build_year(2026, raw, tmp_path / "d")
    e = read(tmp_path / "d" / "2026" / "despesas_por_candidato.csv")
    assert e.values.tolist() == [["1", "60000.00", "59000.00"], ["2", "300.00", "300.00"]]
    f = read(tmp_path / "d" / "2026" / "fornecedores.csv")
    assert f.values.tolist() == [["13347016000117", "FACEBOOK LTDA", "Publicidade", "60000.00", "1"]]   # companies only


def test_rebuild_is_byte_identical(raw, tmp_path):
    b.build_year(2026, raw, tmp_path / "d")
    before = {p: p.read_bytes() for p in (tmp_path / "d").rglob("*.csv")}
    b.build_year(2026, raw, tmp_path / "d")
    assert {p: p.read_bytes() for p in (tmp_path / "d").rglob("*.csv")} == before
