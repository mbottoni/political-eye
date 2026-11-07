import json

import pandas as pd

from politicaleye.senado import fetch
from politicaleye.senado.build import build_year

from .conftest import senadores, write_raw_2025


def read(data, sub, month):
    return pd.read_csv(data / sub / f"{month}.csv", dtype=str, keep_default_na=False)


def test_votacoes(built):
    vt = read(built, "votacoes", "2025-03")
    assert vt.id.tolist() == ["11", "13", "12"]      # by day, then session, then id; 14, 15 dropped
    secret = vt.set_index("id").loc["13"]
    assert (secret.secreta, secret.votos_sim, secret.votos_nao, secret.votos_abstencao) == ("1", "3", "1", "0")
    open_ = vt.set_index("id").loc["12"]
    assert (open_.secreta, open_.votos_sim, open_.votos_nao) == ("0", "2", "3")   # counted from the rows
    assert vt.set_index("id").loc["11"].descricao == "Votação nominal 11"
    assert vt.set_index("id").loc["11"].processo_id == "911"
    assert read(built, "votacoes", "2025-04").id.tolist() == ["16"]


def test_votes(built):
    v = read(built, "votes", "2025-03")
    assert v.columns.tolist() == ["votacao_id", "senador_id", "voto", "partido", "uf"]
    assert v[v.votacao_id == "12"].senador_id.tolist() == ["1", "2", "3", "4", "5"]   # duplicate dropped
    assert v[v.votacao_id == "13"].voto.unique().tolist() == ["Votou"]               # secret: attendance only
    apr = read(built, "votes", "2025-04").set_index("senador_id")
    assert apr.loc["3", "partido"] == "S/Partido" and apr.loc["4", "partido"] == ""   # as published


def test_dropped_and_counted(tmp_path, capsys):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)
    r = build_year(2025, raw, data)
    assert (r["votacoes_misdated"], r["votacoes_without_votes"], r["votacoes_off_year"], r["votes_duplicate"]) == (1, 1, 1, 1)
    assert r["authorship_off_year"] == 1 and r["authorship_party_unparsed"] == 1
    assert r["authorship_not_senate"] == 3   # the veto twice, the Câmara bill once


def test_authorship(built):
    au = read(built, "authorship", "2025-03")
    assert au.columns.tolist() == ["processo_id", "sigla_tipo", "materia", "data_apresentacao", "senador_id",
                                   "partido", "lider"]
    assert au[["processo_id", "senador_id"]].values.tolist() == [
        ["501", "1"], ["501", "2"], ["501", "3"], ["504", "1"], ["504", "4"], ["504", "5"]]
    assert au.sigla_tipo.tolist() == ["PL"] * 3 + ["PEC"] * 3
    # party at the time, from the authors' text; Eva is behind "e outros"
    assert au.partido.tolist() == ["PT", "PT", "PL", "PT", "PL", ""]
    assert au.lider.unique().tolist() == ["0"]
    apr = read(built, "authorship", "2025-04")
    assert apr[["sigla_tipo", "materia", "partido", "lider"]].values.tolist() == [["RQS", "RQS 3/2025", "PT", "1"]]


def test_party_in_text():
    from politicaleye.senado.build import party_in_text

    text = "Líder do PSD Omar Aziz (PSD/AM), Senadora Teresa Leitão (PT/PE), Senador Omar (PL/RJ)"
    assert party_in_text(text, "Omar Aziz") == ("PSD", True)
    assert party_in_text(text, "Teresa Leitão") == ("PT", False)
    assert party_in_text(text, "Omar") == ("PL", False)          # whole names only
    assert party_in_text("Senador Camilo Santana (PT/CE)", "Omar Aziz") == ("", False)


def test_senators(built):
    s = read(built, "senators", "2025-03").set_index("senador_id")
    assert s.index.tolist() == ["1", "2", "3", "4", "5"]
    assert s.loc["5"].tolist() == ["Eva", "MDB", "SP", "2", "1"]   # nome, partido, uf, n_votes, n_authored
    apr = read(built, "senators", "2025-04").set_index("senador_id")
    assert apr.loc["3", "partido"] == "S/Partido" and apr.loc["4", "partido"] == ""
    assert apr.loc["1", ["n_votes", "n_authored"]].tolist() == ["1", "1"]


def test_rebuild_is_byte_identical_and_drops_stale_months(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)
    build_year(2025, raw, data)
    before = {p: p.read_bytes() for p in data.rglob("*.csv")}
    (data / "votes" / "2025-11.csv").write_text("stale\n")
    build_year(2025, raw, data)
    assert {p: p.read_bytes() for p in data.rglob("*.csv")} == before


def test_legislaturas():
    assert fetch.legislaturas(2015) == [54, 55]   # January is still the 54th
    assert fetch.legislaturas(2016) == [55]
    assert fetch.legislaturas(2027) == [57, 58]


def test_fetch_year(monkeypatch, tmp_path):
    asked = []

    def fake(url, **kw):
        asked.append(url)
        if "/votacao?" in url:
            return b"[]"
        if "orientacaoBancada" in url:
            return b'{"votacoes": []}'
        if "/senador/lista/legislatura/" in url:
            return json.dumps(senadores(["1", "2"])).encode()
        return b"[]"

    monkeypatch.setattr(fetch, "get_bytes", fake)
    monkeypatch.setattr(fetch, "PAUSE", 0)
    rec = fetch.fetch_year(2026, tmp_path)
    assert asked[0] == "https://legis.senado.leg.br/dadosabertos/votacao?dataInicio=2026-01-01&dataFim=2026-12-31"
    assert asked[1].endswith("/plenario/votacao/orientacaoBancada/20260101/20261231")
    assert asked[2].endswith("/senador/lista/legislatura/57.json?exercicio=S")
    assert asked[3].endswith("/processo?codigoParlamentarAutor=1&dataInicioApresentacao=2026-01-01&dataFimApresentacao=2026-12-31")
    assert sorted(rec) == ["autoria-2026", "orientacao-2026", "senadores-57", "votacao-2026"]
    assert rec["autoria-2026"]["files"] == 2
    assert (tmp_path / "autoria" / "2026" / "2.json").read_text() == "[]"
