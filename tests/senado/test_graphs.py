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
