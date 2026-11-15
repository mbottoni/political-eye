import pandas as pd

from politicaleye.senado import graphs as sg
from politicaleye.senado.build import build_year
from politicaleye.views import senadores as v
from tests.senado.conftest import write_raw_2025


def w(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def fixture(tmp_path):
    """Senators 1-5 voting in March and April 2025 (tests/senado/conftest.py), linked to amendments and Senate races."""
    data = tmp_path / "data"
    write_raw_2025(tmp_path / "raw")
    build_year(2025, tmp_path / "raw", data / "senado")
    sg._load.cache_clear()
    sg._window.cache_clear()
    w(data / "ref" / "politicians.csv", pd.DataFrame(
        [(f"senado:{i}", "senado", str(i), n, "") for i, n in enumerate(["Ana", "Bia", "Caio", "Davi", "Eva"], 1)]
        + [("senado:1", "emendas", "900", "ANA", "x"), ("senado:1", "tse", "s18", "ANA", "x"), ("senado:1", "tse", "s22", "ANA", "x"),
           ("senado:1", "tse", "s26", "ANA", "x"), ("senado:2", "tse", "b18", "BIA", "x")],
        columns=["pessoa", "fonte", "id", "nome", "metodo"]))
    w(data / "emendas" / "por_autor.csv", pd.DataFrame({
        "autor_codigo": ["900", "900"], "autor": "ANA", "ano": ["2024", "2022"], "tipo": ["especial", "individual"],
        "emendas": ["2", "9"], "empenhado": ["300.00", "999.00"], "liquidado": "0.00", "pago": ["120.50", "50.00"]}))
    cand = {2018: [("s18", "1º Suplente", "15", "NÃO ELEITO", "NINGUEM"), ("b18", "1º Suplente", "45", "ELEITO", "BIA"),
                   ("t18", "Senador", "45", "ELEITO", "TITULAR")],
            2022: [("s22", "Senador", "13", "ELEITO", "ANA")],
            2026: [("s26", "Senador", "13", "NÃO ELEITO", "ANA")]}
    for y, rows in cand.items():
        c = pd.DataFrame(rows, columns=["sq_candidato", "cargo", "numero", "resultado", "nome_urna"]).assign(uf="SP", partido="PT", nome="x")
        w(data / "tse" / str(y) / "candidatos.csv", c)
        w(data / "tse" / str(y) / "receitas_por_candidato.csv", pd.DataFrame({
            "sq_candidato": c.sq_candidato, "total": [f"{1000 * (i + 1)}.00" for i in range(len(c))], "origem_partido": "500.00",
            "fonte_fefc": "400.00", "origem_proprios": "0.00", "n_doadores_pf": "3"}))
    return data


def test_seat_elections():
    assert v.seat_elections(57) == [2018, 2022] and v.seat_elections(56) == [2014, 2018]


def test_view(tmp_path):
    data = fixture(tmp_path)
    out = v.build(57, data)
    assert out.columns.tolist() == v.COLS
    s = out.set_index("senador_id")
    assert s.index.tolist() == ["1", "2", "3", "4", "5"]                     # everyone in office at a roll call
    ana = s.loc["1"]
    # v11 and v12 in March (PT oriented Sim on both; the Government Sim, then Não), v16 in April.
    assert (ana.n_votes, ana.n_party, ana.with_party, ana.n_gov, ana.with_gov) == ("3", "2", 1.0, "2", 0.5)
    assert (ana.emendas, ana.emendas_empenhado, ana.emendas_pago) == (2, "300.00", "120.50")   # 2022's budget is the 56th's
    # The 2022 race she won, not the 2018 one she lost as a suplente (2026 is not a seat race of the 57th).
    assert (ana.campanha_ano, ana.campanha_cargo, ana.campanha_sq_candidato, ana.campanha_total) == ("2022", "Senador", "s22", "1000.00")
    assert (s.loc["2", "campanha_cargo"], s.loc["2", "campanha_ano"]) == ("1º Suplente", "2018")
    assert s.loc["3", "campanha_sq_candidato"] == "" and s.loc["4", "partido"] == "PL"   # April's record has no party
    sg._load.cache_clear()
    sg._window.cache_clear()
