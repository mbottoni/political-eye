"""Mayors from a tiny TSE candidates zip: regular and supplementary elections, matched to IBGE codes."""

import csv
import io
import zipfile

import pandas as pd

from politicaleye.ref import prefeitos as p

HEAD = ["NR_TURNO", "SG_UF", "SG_UE", "NM_UE", "DS_CARGO", "DS_SIT_TOT_TURNO", "SG_PARTIDO", "NM_URNA_CANDIDATO", "SQ_CANDIDATO",
        "DS_GENERO", "DS_COR_RACA", "CD_ELEICAO", "DS_ELEICAO", "DT_ELEICAO", "NR_CPF_CANDIDATO"]


def row(turno, uf, ue, name, cargo, sit, party, cand, eleicao="Eleições Municipais 2020", date="15/11/2020"):
    return [turno, uf, ue, name, cargo, sit, party, f"MAYOR {cand}", cand, "FEMININO", "PARDA", "1", eleicao, date, "12345678901"]


def write(raw, year, rows):
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(HEAD)
    w.writerows(rows)
    raw.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(raw / f"consulta_cand_{year}.zip", "w") as z:
        z.writestr(f"consulta_cand_{year}_BRASIL.csv", s.getvalue().encode("latin1"))


def test_norm():
    assert p.norm("Santa Bárbara d'Oeste") == "SANTA BARBARA DOESTE" and p.norm("Grão-Pará") == "GRAO PARA"


def test_build_and_mayor_by_year(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write(raw, 2020, [
        row("1", "SP", "71072", "SÃO PAULO", "PREFEITO", "2º TURNO", "MDB", "1"),
        row("2", "SP", "71072", "SÃO PAULO", "PREFEITO", "ELEITO", "MDB", "1"),
        row("1", "SP", "61000", "EMBU", "PREFEITO", "ELEITO", "PT", "2"),
        row("1", "SP", "61000", "EMBU", "VEREADOR", "ELEITO", "PL", "3"),
        row("1", "SP", "61000", "EMBU", "PREFEITO", "ELEITO", "PL", "4", eleicao="Eleição suplementar de Embu", date="07/04/2022"),
    ])
    entes = tmp_path / "entes.csv"
    pd.DataFrame({"cod_ibge": ["3550308", "3515004"], "ente": ["São Paulo", "Embu das Artes"], "uf": ["SP", "SP"]}).to_csv(entes, index=False)
    r = p.build(raw, data, entes)
    assert r["2020"] == 2 and r["suplementares"] == 1 and r["unmatched"] == 0
    t = pd.read_csv(data / "prefeitos.csv", dtype=str, keep_default_na=False)
    assert "12345678901" not in (data / "prefeitos.csv").read_text()   # no CPF kept
    assert set(t.cod_ibge) == {"3550308", "3515004"}
    y = p.mayor_by_year(t, [2021, 2022, 2023]).set_index(["exercicio", "cod_ibge"]).partido
    assert y[(2021, "3515004")] == "PT" and y[(2022, "3515004")] == "PT" and y[(2023, "3515004")] == "PL"
    assert y[(2023, "3550308")] == "MDB"
