from pathlib import Path

import pandas as pd

from politicaleye.camara.build import build_year

from .conftest import write_raw_2025


def read(data: Path, sub: str, month: str) -> pd.DataFrame:
    return pd.read_csv(data / sub / f"{month}.csv", dtype=str, keep_default_na=False)


def test_months_and_filters(built):
    assert sorted(p.stem for p in (built / "votes").glob("*.csv")) == ["2025-03", "2025-04"]
    vt = read(built, "votacoes", "2025-03")
    # committee vote (v4) and symbolic vote (v7) are out; off-year v6 is out
    assert vt.id.tolist() == ["v1", "v2", "v3"]
    assert vt.descricao[0] == 'Primeira; com "aspas"\ne quebra'


def test_votes_dedup_and_numeric_order(built):
    v = read(built, "votes", "2025-03")
    v1 = v[v.votacao_id == "v1"]
    assert v1.deputado_id.tolist() == ["10", "20", "30", "40", "100"]  # numeric, not "100" < "20"
    assert len(v1) == 5  # duplicate row for deputy 10 collapsed


def test_deputies_latest_party_and_counts(built):
    d = read(built, "deputies", "2025-03").set_index("deputado_id")
    assert d.loc["20", "partido"] == "B"
    assert d.loc["100", "n_votes"] == "2"
    assert d.loc["100", "n_authored"] == "1"
    assert d.index.tolist() == ["10", "20", "30", "40", "100"]


def test_authorship_filters(built):
    a = read(built, "authorship", "2025-03")
    assert sorted(set(a.proposicao_id), key=int) == ["1", "2", "3", "4"]  # 5 off-year, 999 unknown
    assert "" not in set(a.deputado_id)
    assert a.data_apresentacao.str.len().eq(10).all()


def test_rebuild_is_byte_identical_and_removes_stale(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)
    stale = data / "votes" / "2025-07.csv"
    stale.parent.mkdir(parents=True)
    stale.write_text("old\n")
    build_year(2025, raw, data)
    assert not stale.exists()
    first = {p: p.read_bytes() for p in data.rglob("*.csv")}
    report = build_year(2025, raw, data)
    assert {p: p.read_bytes() for p in data.rglob("*.csv")} == first
    assert report["votes_duplicate"] == 1
    assert report["votacoes_off_year"] == 1
    assert report["authorship_off_year"] == 1
    assert report["authorship_no_proposicao"] == 1

