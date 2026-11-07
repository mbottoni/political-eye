"""Tiny sanctions zips in the real format: cp1252, ';', every field quoted."""

import csv
import io
import zipfile

import pandas as pd
import pytest

from politicaleye.sancoes import build as b
from politicaleye.sancoes import fetch

CEIS = ["CADASTRO", "CÓDIGO DA SANÇÃO", "TIPO DE PESSOA", "CPF OU CNPJ DO SANCIONADO", "NOME DO SANCIONADO",
        "NOME INFORMADO PELO ÓRGÃO SANCIONADOR", "RAZÃO SOCIAL - CADASTRO RECEITA", "NÚMERO DO PROCESSO",
        "CATEGORIA DA SANÇÃO", "DATA INÍCIO SANÇÃO", "DATA FINAL SANÇÃO", "FUNDAMENTAÇÃO LEGAL", "OBSERVAÇÕES"]
CNEP = CEIS[:9] + ["VALOR DA MULTA"] + CEIS[9:]
ACORDOS = ["ID DO ACORDO", "CNPJ DO SANCIONADO", "RAZÃO SOCIAL – CADASTRO RECEITA", "DATA DE INÍCIO DO ACORDO",
           "SITUAÇÃO DO ACORDO DE LENIÊNICA", "TERMOS DO ACORDO"]
EFEITOS = ["ID DO ACORDO", "EFEITO DO ACORDO DE LENIENCIA", "COMPLEMENTO"]
LAW = "LEI 8666 - ART. 87, III - " + "SUSPENSÃO TEMPORÁRIA " * 20


def table(header, rows) -> bytes:
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return s.getvalue().encode("cp1252")


def ceis_row(code, tipo, doc, name, obs="", process="123"):
    return ["CEIS", code, tipo, doc, name, name, "" if tipo == "F" else name, process,
            "Suspensão", "07/04/2026", "07/04/2029", LAW, obs]


def write(raw, ceis_rows, acordos_rows=None):
    raw.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(raw / "ceis.zip", "w") as z:
        z.writestr("20261106_CEIS.csv", table(CEIS, ceis_rows))
    with zipfile.ZipFile(raw / "cnep.zip", "w") as z:
        z.writestr("20261106_CNEP.csv", table(CNEP, [
            ["CNEP", "138362", "J", "11338577000124", "CASSOL LTDA", "CASSOL LTDA", "CASSOL LTDA", "PAR-1",
             "Multa", "36.680,49", "01/07/2022", "", LAW, ""]]))
    with zipfile.ZipFile(raw / "acordos-leniencia.zip", "w") as z:
        z.writestr("20261106_Acordos.csv", table(ACORDOS, acordos_rows or [
            ["100001", "EXBILFINGER", "BILFINGER GMBH", "14/08/2017", "Cumprido", "Multa de 2.658.169,73 EUROS"]]))
        z.writestr("20261106_Efeitos.csv", table(EFEITOS, [["100001", "Integridade", "Treinamentos"]]))


DAY1 = {"ceis": "2026-11-06", "cnep": "2026-11-06", "acordos-leniencia": "2026-11-06"}
DAY2 = {"ceis": "2026-11-07", "cnep": "2026-11-07", "acordos-leniencia": "2026-11-07"}
FIRST = [
    ceis_row("402723", "F", "86246224091", "VINICIUS DALL OGLIO"),
    ceis_row("379716", "J", "07523186000102", "CHRISTIAN MARIANO BATISTA 10036683647",
             obs="sócio Fábio Tonassi (CPF nº 018.714.277-70) e a empresa 12.345.678/0001-90. Ex-prefeito: CPF "
                 "064.748.268-19. Ré: CPF 249.674.098-060, em 07/04/2026, processo 0012345-67.2020.8.26.0100"),
    ceis_row("100", "", "12345678901", "SEM TIPO", process="321.784.099-20"),
    ceis_row("101", "J", "07523186000103", "EMPRESA SA", process="20240586292"),
]


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def test_slug_and_masks():
    assert b.slug("CÓDIGO DA SANÇÃO") == "codigo_da_sancao"
    assert b.slug("RAZÃO SOCIAL – CADASTRO RECEITA") == "razao_social_cadastro_receita"
    assert b.mask_cpf("86246224091") == "***.462.240-**"
    assert b.mask_cpf("862.462.240-91") == "***.462.240-**"
    assert b.mask_cpf("1234567") == "*******"


def test_no_full_cpf_is_ever_written(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write(raw, FIRST)
    b.build(raw, data, DAY1)
    c = read(data / "ceis.csv").set_index("codigo_da_sancao")
    assert c.loc["402723", "cpf_ou_cnpj_do_sancionado"] == "***.462.240-**"
    assert c.loc["402723", "nome_do_sancionado"] == "VINICIUS DALL OGLIO"      # the name is kept
    assert c.loc["379716", "cpf_ou_cnpj_do_sancionado"] == "07523186000102"    # a company's CNPJ is kept
    assert c.loc["379716", "nome_do_sancionado"] == "CHRISTIAN MARIANO BATISTA ***.366.836-**"
    assert c.loc["379716", "observacoes"] == (
        "sócio Fábio Tonassi (CPF nº ***.714.277-**) e a empresa 12.345.678/0001-90. Ex-prefeito: CPF ***.748.268-**. "
        "Ré: CPF ***.674.098-**, em 2026-04-07, processo 0012345-67.2020.8.26.0100".replace("2026-04-07", "07/04/2026"))
    assert c.loc["100", "cpf_ou_cnpj_do_sancionado"] == "***.456.789-**"       # no type, CPF-shaped
    assert c.loc["100", "numero_do_processo"] == "***.784.099-**"
    assert c.loc["101", "numero_do_processo"] == "20240586292"                # bare 11 digits: a process number
    text = "".join(p.read_text(encoding="utf-8") for p in data.rglob("*.csv"))
    for cpf in ("86246224091", "10036683647", "018.714.277-70", "12345678901", "321.784.099-20", "064.748.268-19",
                "249.674.098-060"):
        assert cpf not in text


def test_tables(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write(raw, FIRST)
    r = b.build(raw, data, DAY1)
    c = read(data / "ceis.csv")
    assert c.codigo_da_sancao.tolist() == ["100", "101", "379716", "402723"]
    assert c.data_inicio_sancao.unique().tolist() == ["2026-04-07"]
    law = read(data / "ref" / "fundamentacoes.csv")
    assert len(law) == 1 and c.fundamentacao_legal.unique().tolist() == law.id.tolist()
    assert read(data / "cnep.csv").valor_da_multa.tolist() == ["36680.49"]
    a = read(data / "leniencia.csv")
    assert a.columns.tolist()[:3] == ["id_do_acordo", "cnpj_do_sancionado", "razao_social_cadastro_receita"]
    assert a.data_de_inicio_do_acordo.tolist() == ["2017-08-14"]
    assert read(data / "leniencia_efeitos.csv").efeito_do_acordo_de_leniencia.tolist() == ["Integridade"]
    assert r["ceis"] == 4 and r["ceis_people"] == 2
    assert read(data / "changes.csv").empty                                   # the first snapshot is a baseline


def test_cepim_key(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write(raw, FIRST)
    head = ["CNPJ ENTIDADE", "NOME ENTIDADE", "NÚMERO CONVÊNIO", "ÓRGÃO CONCEDENTE", "MOTIVO DO IMPEDIMENTO"]
    rows = [["00002444000166", "SINDICATO", "644382", "MAPA", "SEM CONTAS"],
            ["00002444000166", "SINDICATO", "629097", "MAPA", "NÃO EXECUTOU"]]
    with zipfile.ZipFile(raw / "cepim.zip", "w") as z:
        z.writestr("20261028_CEPIM.csv", table(head, rows))
    b.build(raw, data, {**DAY1, "cepim": "2026-10-28"})
    with zipfile.ZipFile(raw / "cepim.zip", "w") as z:
        z.writestr("20261104_CEPIM.csv", table(head, rows[:1]))
    r = b.build(raw, data, {**DAY2, "cepim": "2026-11-04"})
    assert r["cepim"] == 1 and r["cepim_duplicate_keys"] == 0
    ch = read(data / "changes.csv")
    assert ch[ch.lista == "cepim"][["data", "codigo", "mudanca", "documento", "nome"]].values.tolist() == [
        ["2026-11-04", "629097", "saiu", "00002444000166", "SINDICATO"]]


def test_changes_are_dated_by_snapshot(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write(raw, FIRST)
    b.build(raw, data, DAY1)
    write(raw, FIRST[1:] + [ceis_row("500", "J", "11111111000111", "NOVA LTDA")],
          acordos_rows=[["100001", "EXBILFINGER", "BILFINGER GMBH", "14/08/2017", "Cumprido", "x"],
                        ["100002", "22641641000168", "AMBIENTAL LTDA", "27/05/2019", "Em Execução", "y"]])
    b.build(raw, data, DAY2)
    ch = read(data / "changes.csv")
    assert ch.columns.tolist() == b.CHANGES
    assert ch[["data", "lista", "codigo", "mudanca", "documento"]].values.tolist() == [
        ["2026-11-07", "ceis", "500", "entrou", "11111111000111"],
        ["2026-11-07", "ceis", "402723", "saiu", "***.462.240-**"],
        ["2026-11-07", "leniencia", "100002", "entrou", "22641641000168"],
    ]
    before = (data / "changes.csv").read_bytes()
    b.build(raw, data, DAY2)                                                  # same snapshot again
    assert (data / "changes.csv").read_bytes() == before


def test_latest_date(monkeypatch):
    page = b'<script> var arquivos = [];\n arquivos.push({"ano" : "2026", "mes" : "10", "dia" : "28", "origem" :  "CEPIM"});'
    monkeypatch.setattr(fetch, "get_bytes", lambda url, **kw: page)
    assert fetch.latest_date("cepim") == "20261028"
    monkeypatch.setattr(fetch, "get_bytes", lambda url, **kw: b"<html>Human Verification</html>")
    with pytest.raises(RuntimeError, match="no date"):
        fetch.latest_date("cepim")
