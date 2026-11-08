import pandas as pd

from politicaleye.camara import graphs
from politicaleye.camara.build import build_year
from politicaleye.site import orientacoes as so
from tests.camara.conftest import write_raw_2025


def test_build_on_fixture(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)
    build_year(2025, raw, data / "camara")
    graphs._load.cache_clear()
    r = so.build(data)
    out = data / "site" / "orientacoes"
    p = pd.read_csv(out / "partidos.csv", dtype=str, keep_default_na=False).set_index(["month", "partido"])
    # March: P1 is deputies 10, 30, 40 (see tests/camara/test_orientations.py); the government
    # oriented in v1 and v2, and only deputy 10 followed it both times: 2 of 6.
    assert p.loc[("2025-03", "P1"), "with_gov"] == "0.3333"
    assert p.loc[("2025-03", "P1"), "deputados"] == "3"
    k = pd.read_csv(out / "orientacoes.csv", dtype=str).set_index(["legislatura", "partido"])
    assert ("57", "Governo") in k.index and ("57", "P1") in k.index   # leaderships under one name
    assert (out / "deputados" / "57.csv").exists() and (out / "deputados_mes" / "2025.csv").exists()
    assert r["months"] == 2
    graphs._load.cache_clear()
