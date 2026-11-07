"""The recorded blocs API, completing cut-off bloc names, and the party-majority measure."""

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from politicaleye.camara import blocos as b
from politicaleye.camara import graphs, summary
from politicaleye.camara import orientations as o
from politicaleye.io import write_csv

API = "https://example.test/api/v2"


def fake_api(monkeypatch, listing: dict[int, list[tuple[str, str, bool, list[str]]]]):
    """``listing``: legislatura -> [(id, nome, federacao, partidos)], as the API answers."""
    docs = {}
    for leg, rows in listing.items():
        docs[f"{API}/blocos?idLegislatura={leg}&itens=100"] = {"dados": [
            {"id": i, "nome": n, "idLegislatura": str(leg), "federacao": f} for i, n, f, _ in rows]}
        for i, _, _, parts in rows:
            docs[f"{API}/blocos/{i}/partidos"] = {"dados": [{"id": 1, "sigla": p} for p in parts]}
    monkeypatch.setattr(b, "get_json", lambda url: docs.get(url))


LEG57 = [
    ("589", "UNIÃO, PP, PSD, REPUBLICANOS, MDB, Federação PSDB CIDADANIA, PODE", False,
     ["PSDB", "CIDADANIA", "UNIÃO", "PP", "REPUBLICANOS", "PSD", "MDB", "PODE"]),
    ("590", "AVANTE, SOLIDARIEDADE, PRD", False, []),   # the API lists no partidos for it
    ("585", "Federação PSDB CIDADANIA", True, ["PSDB", "CIDADANIA"]),
]


def record(monkeypatch, data, day, listing):
    fake_api(monkeypatch, {55: [("1", "PSD", False, ["PSD"])], 56: [("2", "PDT", False, ["PDT"])], 57: listing})
    return b.update(data, dt.date.fromisoformat(day), api=API)


def table(data, name):
    return pd.read_csv(data / "blocos" / f"{name}.csv", dtype=str, keep_default_na=False)


def test_first_snapshot(monkeypatch, tmp_path):
    ch = record(monkeypatch, tmp_path, "2026-11-07", LEG57)
    assert ch == {"blocos_listed": 5, "blocos_unlisted": 0, "members_listed": 15, "members_unlisted": 0}
    bl, mem = table(tmp_path, "blocos"), table(tmp_path, "members")
    assert bl.columns.tolist() == b.BLOCOS_COLS and mem.columns.tolist() == b.MEMBERS_COLS
    assert bl.bloco_id.tolist() == ["1", "2", "585", "589", "590"]
    assert set(mem[mem.bloco_id == "590"].partido) == {"AVANTE", "SOLIDARIEDADE", "PRD"}   # from the name
    assert (bl.listed_from == "2026-11-07").all() and (bl.listed_until == "").all()


def test_changes_are_dated_and_nothing_else_moves(monkeypatch, tmp_path):
    record(monkeypatch, tmp_path, "2026-11-07", LEG57)
    first = (tmp_path / "blocos" / "members.csv").read_bytes()
    assert record(monkeypatch, tmp_path, "2026-11-08", LEG57)["members_listed"] == 0
    assert (tmp_path / "blocos" / "members.csv").read_bytes() == first   # no change, no diff

    # PODE leaves 589 and a new bloc forms; then PODE comes back.
    later = [(i, n, f, [p for p in parts if p != "PODE"]) for i, n, f, parts in LEG57]
    later.append(("591", "PL, NOVO", False, ["PL", "NOVO"]))
    assert record(monkeypatch, tmp_path, "2026-11-20", later) == {
        "blocos_listed": 1, "blocos_unlisted": 0, "members_listed": 2, "members_unlisted": 1}
    record(monkeypatch, tmp_path, "2026-12-01", LEG57)
    mem = table(tmp_path, "members")
    pode = mem[(mem.bloco_id == "589") & (mem.partido == "PODE")]
    assert pode[["listed_from", "listed_until"]].values.tolist() == [["2026-11-07", "2026-11-20"], ["2026-12-01", ""]]
    bl = table(tmp_path, "blocos")
    assert bl[bl.bloco_id == "591"][["listed_from", "listed_until"]].values.tolist() == [["2026-11-20", "2026-12-01"]]


def test_an_empty_listing_is_not_recorded(monkeypatch, tmp_path):
    record(monkeypatch, tmp_path, "2026-11-07", LEG57)
    with pytest.raises(RuntimeError, match="no blocs"):
        record(monkeypatch, tmp_path, "2026-11-08", [])
    assert (table(tmp_path, "blocos").listed_until == "").all()


def test_in_effect_days():
    df = pd.DataFrame({"listed_from": ["2026-11-07", "2026-11-20"], "listed_until": ["2026-11-25", ""]})
    on = lambda day, **kw: b.in_effect(df, day, **kw).listed_from.tolist()  # noqa: E731
    assert on("2026-11-06") == []                       # before recording
    assert on("2026-11-06", before_recording=True) == ["2026-11-07"]
    assert on("2026-11-19") == ["2026-11-07"]
    assert on("2026-11-20") == ["2026-11-07", "2026-11-20"]
    assert on("2026-11-23") == ["2026-11-07", "2026-11-20"]
    assert on("2026-11-24") == ["2026-11-20"]           # left on the 24th or overnight: not certain
    assert on("2026-11-19", before_recording=True) == ["2026-11-07"]  # a later row never counts early


def test_bloc_elements():
    assert o.bloc_elements("Bl UniPpFdrPsdbCid...") == (
        frozenset({"UNIÃO"}), frozenset({"PP"}), frozenset({"PSDB", "CIDADANIA"}))
    assert o.bloc_elements("PmdbPen") == (frozenset({"MDB"}), frozenset({"PATRIOTA"}))
    assert o.bloc_elements("PT") is None and o.bloc_elements("Fdr PT-PCdoB-PV") is None


# ---------------------------------------------------- a month on disk, tidy

MONTH = "2026-11"   # recording started on the 7th
PARTY = {1: "PP", 2: "PP", 3: "PP", 4: "PP", 5: "PSD", 6: "PSD", 7: "S.PART.", 8: "MDB"}
VOTES = {"x": "SSSNNNSS", "y": "SNSNSNNS"}   # deputies 1-8, S = Sim, N = Não


def write_month(data: Path, orientations: list[tuple[str, str, str]]):
    write_csv(pd.DataFrame([("x", "2026-11-03", "2026-11-03T15:00:00", "1", "5", "3", "0", "x"),
                            ("y", "2026-11-20", "2026-11-20T15:00:00", "0", "4", "4", "0", "y")],
                           columns=["id", "data", "hora_registro", "aprovacao", "votos_sim", "votos_nao",
                                    "votos_outros", "descricao"]), data / "votacoes" / f"{MONTH}.csv")
    write_csv(pd.DataFrame([(v, d, "Sim" if c == "S" else "Não", PARTY[d]) for v, cs in VOTES.items()
                            for d, c in enumerate(cs, 1)],
                           columns=["votacao_id", "deputado_id", "voto", "partido"]), data / "votes" / f"{MONTH}.csv")
    write_csv(pd.DataFrame(orientations, columns=["votacao_id", "bancada", "orientacao"]),
              data / "orientations" / f"{MONTH}.csv")
    write_csv(pd.DataFrame(columns=["proposicao_id", "sigla_tipo", "data_apresentacao", "deputado_id",
                                    "ordem_assinatura", "proponente"]), data / "authorship" / f"{MONTH}.csv")
    write_csv(pd.DataFrame([(d, f"D{d}", p, "SP", 2, 0) for d, p in PARTY.items()],
                           columns=["deputado_id", "nome", "partido", "uf", "n_votes", "n_authored"]),
              data / "deputies" / f"{MONTH}.csv")
    graphs._load.cache_clear()
    b.load.cache_clear()


def write_blocs(data: Path, rows: list[tuple[str, str, list[str], str]]):
    """rows: (bloco_id, nome, members, listed_from), all legislatura 57, still listed."""
    write_csv(pd.DataFrame([(i, "57", n, "0", f, "") for i, n, _, f in rows], columns=b.BLOCOS_COLS),
              data / "blocos" / "blocos.csv")
    write_csv(pd.DataFrame([(i, p, f, "") for i, _, ms, f in rows for p in ms], columns=b.MEMBERS_COLS),
              data / "blocos" / "members.csv")


CUT = [("x", "Bl PpPsd...", "Sim"), ("x", "Governo", "Não"), ("y", "Bl PpPsd...", "Sim")]
BLOC = ("900", "PP, PSD, MDB", ["PP", "PSD", "MDB"], b.RECORDING_STARTED)


@pytest.fixture
def month(tmp_path):
    write_month(tmp_path, CUT)
    write_blocs(tmp_path, [BLOC])
    yield tmp_path
    graphs._load.cache_clear()
    b.load.cache_clear()


COLS = ["n_votes", "n_party", "n_with_party", "n_none", "n_unknown"]


def test_cut_off_names_completed_on_recorded_days(month):
    d = o.discipline(MONTH, data_dir=month).set_index("deputado_id")
    assert d.loc[8, COLS].tolist() == [2, 1, 1, 0, 1]     # MDB: unknown on the 3rd, the bloc's on the 20th
    assert d.loc[4, COLS].tolist() == [2, 2, 0, 0, 0]     # PP is in the name itself: both days
    assert d.loc[7, COLS].tolist() == [2, 0, 0, 2, 0]     # no party: nothing to follow, not unknown


def test_listed_and_none_modes(month):
    listed = o.discipline(MONTH, blocs="listed", data_dir=month).set_index("deputado_id")
    assert listed.loc[8, COLS].tolist() == [2, 2, 2, 0, 0]
    never = o.discipline(MONTH, blocs=None, data_dir=month).set_index("deputado_id")
    assert never.loc[8, COLS].tolist() == [2, 0, 0, 0, 2]
    with pytest.raises(ValueError):
        o.discipline(MONTH, blocs="all", data_dir=month)


@pytest.mark.parametrize("blocs, why", [
    ([BLOC, ("901", "PP, PSD, NOVO", ["PP", "PSD", "NOVO"], b.RECORDING_STARTED)], "two blocs match"),
    ([("900", "PSD, PP, MDB", ["PP", "PSD", "MDB"], b.RECORDING_STARTED)], "parties in another order"),
    ([("900", "PP, PSD, MDB", ["PP", "MDB"], b.RECORDING_STARTED)], "members lack a named party"),
    ([("900", "PP, PSD, MDB", ["PP", "PSD", "MDB"], "2026-11-21")], "listed only after the vote"),
])
def test_no_completion_when_uncertain(month, blocs, why):
    write_blocs(month, blocs)
    b.load.cache_clear()
    d = o.discipline(MONTH, blocs="listed", data_dir=month).set_index("deputado_id")
    assert d.loc[8, "n_party"] == 0, why


def test_completion_through_a_federation(tmp_path):
    write_csv(pd.DataFrame([("589", "57", "UNIÃO, PP, Federação PSDB CIDADANIA, PDT", "0", b.RECORDING_STARTED, ""),
                            ("585", "57", "Federação PSDB CIDADANIA", "1", b.RECORDING_STARTED, "")],
                           columns=b.BLOCOS_COLS), tmp_path / "blocos" / "blocos.csv")
    write_csv(pd.DataFrame([(i, p, b.RECORDING_STARTED, "") for i, ps in
                            (("589", ["UNIÃO", "PP", "PSDB", "CIDADANIA", "PDT"]), ("585", ["PSDB", "CIDADANIA"]))
                            for p in ps], columns=b.MEMBERS_COLS), tmp_path / "blocos" / "members.csv")
    b.load.cache_clear()
    ori = pd.DataFrame([("v", "Bl UniPpFdrPsdbCid...", "Sim")], columns=["votacao_id", "bancada", "orientacao"])
    vot = pd.DataFrame({"id": ["v"], "data": ["2026-12-01"]})
    got = o.completions(ori, vot, 57, tmp_path)
    assert got == {("v", "Bl UniPpFdrPsdbCid..."): frozenset({"UNIÃO", "PP", "PSDB", "CIDADANIA", "PDT"})}
    assert o.completions(ori, vot, 56, tmp_path) == {}   # another legislature's bloc
    b.load.cache_clear()


def test_party_majority(month):
    d = o.discipline(MONTH, data_dir=month).set_index("deputado_id")
    cols = ["n_majority", "n_with_majority"]
    # x: PP 1-3 Sim, 4 Não; y: PP 1 Sim, 2 Não, 3 Sim, 4 Não. Each deputy is
    # measured against the *other* PP deputies: in y, 1's others are N, S, N.
    assert d.loc[1, cols].tolist() == [2, 1]
    assert d.loc[2, cols].tolist() == [2, 1]
    assert d.loc[4, cols].tolist() == [2, 0]
    assert d.loc[5, cols].tolist() == [2, 1]     # PSD: the other one is the majority
    assert d.loc[7, cols].tolist() == [0, 0]     # no party
    assert d.loc[8, cols].tolist() == [0, 0]     # the only MDB deputy: no one else
    assert d.loc[4, "with_majority"] == 0


def test_party_majority_ties_are_no_majority(built):
    d = o.discipline("2025-03", data_dir=built).set_index("deputado_id")
    # v1: P1 is 10 Sim, 30 Não, 40 Obstrução; v2: 10 Não, 30 Sim, 40 Sim.
    assert d.loc[10, ["n_majority", "n_with_majority"]].tolist() == [2, 0]
    assert d.loc[30, "n_majority"] == 0 and d.loc[40, "n_majority"] == 0
    assert summary.month_row("2025-03", built)["with_majority"] == 0.0
