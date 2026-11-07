import pandas as pd

from politicaleye.camara import graphs as cg
from politicaleye.views import deputados as v
from tests.camara.conftest import write_raw_2025
from politicaleye.camara.build import build_year


def test_years():
    assert v.election_of(57) == 2022 and v.budget_years(57) == [2024, 2025, 2026, 2027]


def test_view(tmp_path):
    data = tmp_path / "data"
    write_raw_2025(tmp_path / "raw")
    build_year(2025, tmp_path / "raw", data / "camara")
    cg._load.cache_clear()
    (data / "ref").mkdir(parents=True)
    pd.DataFrame([("camara:10", "camara", "10", "Ana", ""), ("camara:10", "emendas", "7", "ANA", "x"),
                  ("camara:10", "tse", "501", "ANA", "x")], columns=["pessoa", "fonte", "id", "nome", "metodo"]
                 ).to_csv(data / "ref" / "politicians.csv", index=False)
    (data / "emendas").mkdir()
    pd.DataFrame({"autor_codigo": ["7", "7"], "autor": "ANA", "ano": ["2024", "2023"], "tipo": "individual",
                  "emendas": ["3", "9"], "empenhado": ["100.50", "999.00"], "liquidado": "0.00",
                  "pago": ["10.25", "0.00"]}).to_csv(data / "emendas" / "por_autor.csv", index=False)
    (data / "tse" / "2022").mkdir(parents=True)
    pd.DataFrame({"sq_candidato": ["501"], "cargo": ["Deputado Federal"], "resultado": ["ELEITO POR QP"]}
                 ).to_csv(data / "tse" / "2022" / "candidatos.csv", index=False)
    pd.DataFrame({"sq_candidato": ["501"], "total": ["1000.00"], "origem_partido": ["900.00"], "fonte_fefc": ["800.00"],
                  "origem_proprios": ["0.00"], "n_doadores_pf": ["3"]}).to_csv(data / "tse" / "2022" / "receitas_por_candidato.csv", index=False)
    out = v.build(57, data)
    assert out.columns.tolist() == v.COLS
    ana = out.set_index("deputado_id").loc["10"]
    assert (ana.pessoa, ana.emendas, ana.emendas_empenhado, ana.emendas_pago) == ("camara:10", 3, "100.50", "10.25")
    assert (ana.campanha_sq_candidato, ana.campanha_total, ana.campanha_partido) == ("501", "1000.00", "900.00")
    assert ana.n_votes == "3" and ana.with_party == 1.0                            # v1, v2 in March; v5 in April
    assert "100" not in out.deputado_id.tolist()                                    # never cast a contested vote
    assert out.set_index("deputado_id").loc["20", "campanha_sq_candidato"] == ""    # no link
    cg._load.cache_clear()
