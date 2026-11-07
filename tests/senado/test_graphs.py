import pytest

from politicaleye.senado import graphs, summary


def test_vote_matrix_drops_secret_and_non_votes(built):
    ids, kept, M = graphs.vote_matrix(graphs.load_month("2025-03", built).votes)
    assert kept.tolist() == ["11", "12"]           # 13 is secret: no Sim/Não to compare
    assert ids.tolist() == [1, 2, 3, 4, 5] and M[4].tolist() == [0, 1]   # P-NRV is not a vote


def test_window_months():
    assert graphs.window_months("2026-11") == [f"2025-12"] + [f"2026-{m:02d}" for m in range(1, 12)]
    assert graphs.window_months("2023-03") == ["2023-02", "2023-03"]     # the 57th began in February 2023
    assert graphs.window_months("2023-01")[0] == "2022-02"              # January is still the 56th
    assert graphs.window_months("2025-03", 1) == ["2025-03"]
    with pytest.raises(ValueError):
        graphs.window_months("2025-03", 0)


def test_window_pools_months(built):
    w = graphs.load_window("2025-04", data_dir=built)
    assert w.votacoes.id.tolist() == ["11", "13", "12", "16"]
    s = w.senators.set_index("senador_id")
    assert s.loc[3, "partido"] == "S/Partido"                  # the latest month's label
    assert s.loc[1, ["n_votes", "n_authored"]].tolist() == [4, 3]       # 11, 13, 12 and 16; 501, 504, 503
    g = graphs.graph("2025-04", data_dir=built, min_shared=2)
    assert g.graph["window_start"] == "2024-05" and g.graph["window"] == 12
    one = graphs.graph("2025-04", window=1, data_dir=built, min_shared=1)
    assert set(one) == {1, 3}                                   # April alone: 4 voted AP


def test_covote(built):
    e = graphs.covote_edges("2025-03", min_shared=2, data_dir=built).set_index(["u", "v"])
    assert e.loc[(1, 2)].agreement == 0.5 and e.loc[(3, 4)].agreement == 1.0
    assert (1, 5) not in e.index                   # only one vote in common
    g = graphs.graph("2025-03", min_shared=2, data_dir=built)
    assert sorted(g.edges()) == [(3, 4)]           # 1-2, 2-3, 2-4 agree on one of two
    assert set(g) == {1, 2, 3, 4}                  # Eva cast one vote: under min_shared
    assert g.nodes[3] == {"name": "Caio", "party": "PL", "uf": "SP"}


def test_cosponsor(built):
    g = graphs.graph("2025-03", "cosponsor", data_dir=built)
    assert sorted(g.edges()) == [(1, 2), (1, 3), (1, 4), (1, 5), (2, 3), (4, 5)]
    assert g.edges[1, 2] == {"n_items": 1, "weight": 0.5}
    capped = graphs.graph("2025-03", "cosponsor", max_authors=2, data_dir=built)
    assert capped.number_of_edges() == 0 and capped.number_of_nodes() == 5


def test_aligned_and_errors(built):
    gv, gc = graphs.aligned("2025-03", min_shared=2, data_dir=built)
    assert set(gv) == set(gc) == {1, 2, 3, 4}
    with pytest.raises(ValueError):
        graphs.graph("2025-03", "other", data_dir=built)


def test_index(built):
    df = summary.build_index(built)
    assert df.month.tolist() == ["2025-03", "2025-04"]
    row = df.set_index("month").loc["2025-03"]
    assert (row.votacoes, row.votacoes_secret, row.votacoes_contested, row.items_signed, row.items_cosigned) == (
        3, 1, 2, 2, 2)
    assert row.cosponsor_edges == 6 and row.legislatura == 57 and row.window_start == "2024-04"
    apr = df.set_index("month").loc["2025-04"]
    assert (apr.votacoes, apr.items_signed) == (4, 3)          # March and April pooled
    assert (built / "index.csv").read_text().startswith("month,legislatura,window_start,votacoes,")


def test_orientations_table(built):
    from .test_build import read
    t = read(built, "orientations", "2025-03")
    assert t.columns.tolist() == ["votacao_id", "bancada", "orientacao"]
    assert t.values.tolist() == [["11", "Governo", "SIM"], ["11", "MDB", "LIVRE"], ["11", "PL", "NÃO"], ["11", "PT", "SIM"],
                                 ["12", "Governo", "NÃO"], ["12", "PT", "SIM"], ["12", "Progressistas", "SIM"]]
    assert read(built, "votacoes", "2025-03").set_index("id").sequencial.to_dict() == {"11": "4011", "13": "", "12": "4012"}


def test_discipline(built):
    from politicaleye.senado import orientations as o
    d = o.discipline("2025-03", data_dir=built).set_index("senador_id")
    cols = ["n_votes", "n_party", "n_with_party", "n_free", "n_none", "n_gov", "n_with_gov", "n_majority", "n_with_majority"]
    # 11: Ana S, Bia S, Caio N, Davi N; 12: Ana S, Bia N, Caio N, Davi N, Eva S
    assert d.loc[1, cols].tolist() == [2, 2, 2, 0, 0, 2, 1, 2, 1]   # PT said Sim twice; Bia agreed in 11 only
    assert d.loc[2, cols].tolist() == [2, 2, 1, 0, 0, 2, 2, 2, 1]
    assert d.loc[3, cols].tolist() == [2, 1, 1, 0, 1, 2, 1, 2, 2]   # PL oriented in 11 only
    assert d.loc[5, cols].tolist() == [1, 0, 0, 0, 1, 1, 0, 0, 0]   # MDB: no orientation in 12 (free only in 11)
    assert o.party_key("Republica") == "REPUBLICANOS" and o.party_key("PROGRES") == o.party_key("Progressistas") == "PP"


def test_index_orientation_columns(built):
    row = summary.month_row("2025-03", built)
    assert row["oriented_share"] == round(6 / 9, 4)          # PT twice (Ana, Bia), PL once (Caio, Davi)
    assert row["with_gov"] == round(5 / 9, 4)
