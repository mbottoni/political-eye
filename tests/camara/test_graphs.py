import pytest

from politicaleye.camara import graphs as g


def pairs(df, *cols):
    return {(r.u, r.v): tuple(getattr(r, c) for c in cols) for r in df.itertuples()}


def test_vote_matrix_drops_lopsided_and_nonvotes(built):
    ids, kept, M = g.vote_matrix(g.load_month("2025-03", built).votes)
    assert kept.tolist() == ["v1", "v2"]          # v3 was unanimous
    assert ids.tolist() == [10, 20, 30, 40]       # 100 only abstained / Art. 17
    assert M.tolist() == [[1, -1], [1, -1], [-1, 1], [-1, 1]]


def test_covote_counts(built):
    e = g.covote_edges("2025-03", min_shared=2, data_dir=built)
    got = pairs(e, "n_shared", "n_agree")
    assert got == {
        (10, 20): (2, 2), (10, 30): (2, 0), (10, 40): (2, 0),
        (20, 30): (2, 0), (20, 40): (2, 0), (30, 40): (2, 2),
    }


def test_covote_options(built):
    # Obstruction not counted as "no": deputy 40 keeps one vote only.
    e = g.covote_edges("2025-03", min_shared=2, obstruction_as_no=False, data_dir=built)
    assert not any(40 in k for k in pairs(e))
    # lop=0 keeps the unanimous vote
    e = g.covote_edges("2025-03", min_shared=1, lop=0, data_dir=built)
    assert pairs(e, "n_shared", "n_agree")[(10, 30)] == (3, 1)


def test_covote_graph(built):
    G = g.graph("2025-03", "covote", tau=0.8, min_shared=2, data_dir=built)
    assert sorted(G.nodes) == [10, 20, 30, 40]
    assert sorted(G.edges) == [(10, 20), (30, 40)]
    assert G.nodes[20] == {"name": "Bia", "party": "B", "uf": "SP"}
    assert G.edges[10, 20]["agreement"] == 1.0
    assert G.graph["legislatura"] == 57


def test_cosponsor_newman_weights_and_cap(built):
    e = g.cosponsor_edges("2025-03", max_authors=4, data_dir=built)
    got = pairs(e, "n_items", "weight")
    assert got == {(10, 20): (2, 1.5), (10, 30): (1, 0.5), (20, 30): (1, 0.5)}
    uncapped = pairs(g.cosponsor_edges("2025-03", max_authors=None, data_dir=built), "n_items", "weight")
    assert uncapped[(10, 20)] == (3, 1.75)
    assert uncapped[(40, 100)] == (1, 0.25)


def test_cosponsor_types_and_nodes(built):
    G = g.graph("2025-03", "cosponsor", max_authors=4, data_dir=built)
    assert sorted(G.nodes) == [10, 20, 30, 40, 100]   # 100 signed only the PEC
    G = g.graph("2025-03", "cosponsor", types={"PL"}, data_dir=built)
    assert sorted(G.nodes) == [10, 20, 30, 40]
    assert sorted(G.edges) == [(10, 20), (10, 30), (20, 30)]


def test_aligned_shares_vertex_set(built):
    gv, gc = g.aligned("2025-03", min_shared=2, max_authors=4, data_dir=built)
    assert list(gv.nodes) == list(gc.nodes) == [10, 20, 30, 40]
    assert sorted(gc.edges) == [(10, 20), (10, 30), (20, 30)]


def test_month_without_cosigning(built):
    G = g.graph("2025-04", "cosponsor", data_dir=built)
    assert G.number_of_edges() == 0


def test_series_and_months(built):
    assert g.months(built) == ["2025-03", "2025-04"]
    assert [m for m, _ in g.series("covote", start="2025-04", min_shared=1, data_dir=built)] == ["2025-04"]


@pytest.mark.parametrize("month,leg", [
    ("2015-02", 55), ("2019-01", 55), ("2019-02", 56), ("2023-01", 56), ("2023-02", 57), ("2026-11", 57), ("2027-02", 58),
])
def test_legislatura(month, leg):
    assert g.legislatura(month) == leg


def test_bad_kind(built):
    with pytest.raises(ValueError):
        g.graph("2025-03", "friends", data_dir=built)


def test_excluded_types_are_dropped_by_default(built):
    import pandas as pd
    # Re-tag item 2 (a REQ co-signed by 10 and 20) as procedural RPD.
    path = built / "authorship" / "2025-03.csv"
    a = pd.read_csv(path, dtype=str, keep_default_na=False)
    a.loc[a.proposicao_id == "2", "sigla_tipo"] = "RPD"
    a.to_csv(path, index=False, lineterminator="\n")
    g._load.cache_clear()
    default = pairs(g.cosponsor_edges("2025-03", max_authors=4, data_dir=built), "n_items")
    everything = pairs(g.cosponsor_edges("2025-03", max_authors=4, exclude=(), data_dir=built), "n_items")
    assert default[(10, 20)] == (1,) and everything[(10, 20)] == (2,)
