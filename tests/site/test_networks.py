import math

import networkx as nx
import pandas as pd

from politicaleye.site import networks as n


def test_nmi_and_ari():
    a = ["x", "x", "y", "y"]
    assert n.nmi(a, [1, 1, 2, 2]) == 1.0 and n.ari(a, [1, 1, 2, 2]) == 1.0
    assert n.nmi(a, [1, 2, 1, 2]) == 0.0 and n.ari(a, [1, 2, 1, 2]) < 0


def two_parties():
    g = nx.Graph()
    for i in range(1, 7):
        g.add_node(i, party="PT" if i <= 3 else "PL", name=f"m{i}", uf="SP")
    g.add_edges_from([(1, 2), (2, 3), (1, 3), (4, 5), (5, 6), (4, 6)])
    return g


def test_analyse_two_cliques():
    gv = two_parties()
    gc = two_parties()
    votes = pd.DataFrame([(v, d, "Sim" if (d <= 3) == (v % 2 == 0) else "Não") for v in range(6) for d in range(1, 7)],
                         columns=["votacao_id", "deputado_id", "voto"])
    row, members = n.analyse(gv, gc, votes, "deputado_id")
    assert row["cross_party_share"] == 0 and row["communities"] == 2
    assert math.isclose(row["nmi_party"], 1.0) and math.isclose(row["modularity_party"], 0.5)
    assert math.isclose(row["modularity_louvain"], 0.5)
    assert math.isclose(row["overlap_jaccard"], 1.0) and math.isclose(row["qap_r"], 1.0)
    m = members.set_index("id")
    assert (m.cross_degree == 0).all() and m.degree.tolist() == [2] * 6
    assert m.loc[1, "pc1"] < 0 < m.loc[4, "pc1"]          # PT on the negative side, as the explorer draws it


def test_empty_graph():
    row, members = n.analyse(nx.Graph(), nx.Graph(), pd.DataFrame(columns=["votacao_id", "deputado_id", "voto"]), "deputado_id")
    assert row["nodes"] == 0 and members.empty


def test_ideal_by_party():
    m = pd.DataFrame({"month": ["2025-03"] * 4, "partido": ["PT", "PT", "PT", "PL"], "pc1": [-1.0, -2.0, -3.0, 1.0]})
    t = n.ideal_by_party(m)
    assert t.values.tolist() == [["2025-03", "PT", 3, -2.5, -2.0, -1.5]]       # PL has under 3 members
    assert math.isclose(t["median"].iloc[0], -2.0)
