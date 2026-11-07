import math

import pandas as pd
import pytest

from politicaleye.camara import orientations as o

from .test_build import read

# Every CamelCase bloc name seen in Plenário orientations 2015-2026.
BLOCS = """PmdbPpPtbPscPhsPen PrbPtnPmnPrpPsdcPrtbPtcPslPtdoB PpPtbPsc PtbProsPsl PtnPtdoBPsl PtbPros PpAvante
PpPtbPscPhs PscPtb PpPodeAvantePen PrPsdPros PtbProsPslPrp PpPodeAvante PslPpPsd... PrbPtnPmnPrpPsdcPtcPslPtdoB
PpPtnPTdoB PpPTdoB PpPtnPhs... PpPodePTdoB PdtSdPode... NovoCidPv PrbPtnPtdobPsl PdtPodePros... PsdbPsbPpsPv
PrbPtnPmnPtcPtdoBPsl PtbSdPros... PrbPtnPtcPtdoBPsl PrbPtnPmnPrpPsdcPrtb PrbPtnPmnPtcPtdoB PmdbPsdbPp... PsdbPsbPps
PmdbPpPtbDemSdPscPhsPen PpPsdPtn... PrPrbSd PpPodePscAvantePen PrPros PmdbPpDemPsbPdtPodePcdobPscPhsAvantePen
PsdbPrPrbPtbSdPpsProsPslPrp PtPsdPrPdtProsPcdob PmdbPpPtbDem... PtPdtPcdob PsdbPsdPrPrb... PdtAvante PpPrPsd
PdtPros... PpMdbPtb PmdbPen""".split() + [
    "Bl UniPpFdrPsdbCid...", "Bl MdbPsdRepPode", "Bl AvanSolidPrd...", "Bl UniPpPsd...", "Bl PlFdrPtUniPp...",
    "Bl PlFdrPTUniPp...", "Bl MdbPsdRepPodePsc", "Bl PlUniPpPsd...",
]

# Every party name seen, as published.
PARTIES = """PSB PDT PT PSOL PCdoB PL PSDB PSD PV Solidaried Novo DEM PROS PSC MDB PP PSL Podemos PTB Patriota Avante
Republican Rede Cidadania REDE PPS NOVO PR CIDADANIA PRB União REPUBLICANOS PODE SOLIDARIEDADE AVANTE PHS PMDB PMB
PATRIOTA PEN Missão PRP PMN PRD PRTB PPL DC PTC PTdoB""".split()


@pytest.mark.parametrize("name", BLOCS)
def test_every_real_bloc_name_parses(name):
    b = o.decode(name)
    assert b.kind == "bloc" and len(b.members) >= 2
    assert b.complete == (not name.endswith("..."))


@pytest.mark.parametrize("name", PARTIES)
def test_every_real_party_name_is_one_party(name):
    b = o.decode(name)
    assert b.kind == "party" and len(b.members) == 1


def test_decoding_details():
    assert o.decode("PmdbPpPtbPscPhsPen").members == {"MDB", "PP", "PTB", "PSC", "PHS", "PATRIOTA"}
    assert o.decode("Bl PlFdrPTUniPp...").members == {"PL", "PT", "PCDOB", "PV", "UNIÃO", "PP"}
    assert o.decode("Bl UniPpFdrPsdbCid...").members == {"UNIÃO", "PP", "PSDB", "CIDADANIA"}
    assert o.decode("PpPTdoB").members == {"PP", "AVANTE"}
    assert o.decode("Fdr PT-PCdoB-PV") == o.Bancada("Fdr PT-PCdoB-PV", "federation", frozenset({"PT", "PCDOB", "PV"}))
    assert o.decode("GOV.").leadership == o.decode("Governo").leadership == "governo"
    assert o.decode("Oposição").leadership == "oposicao"
    assert o.decode("Bloco Parlamentar") == o.Bancada("Bloco Parlamentar", "bloc", frozenset(), complete=False)


def test_party_labels_match_across_sources():
    # orientation label, then the labels deputies' vote records carry
    assert {o.party_key(x) for x in ("Solidaried", "SOLIDARI", "SOLIDARIED", "SD", "SDD")} == {"SOLIDARIEDADE"}
    assert {o.party_key(x) for x in ("Republican", "REPUBLIC", "REPUBLICANOS", "PRB")} == {"REPUBLICANOS"}
    assert {o.party_key(x) for x in ("Patriota", "PATRI", "PATRIOTA", "PEN")} == {"PATRIOTA"}
    assert {o.party_key(x) for x in ("Podemos", "PODE", "PTN")} == {"PODE"}
    assert o.party_key("PP**") == "PP" and o.party_key("União") == "UNIÃO"
    assert o.party_key("DEM") != o.party_key("UNIÃO")   # a merger, not a rename


def test_applicable_priority_and_conflicts():
    t = pd.DataFrame([
        ("x", "PT", "Sim"), ("x", "Fdr PT-PCdoB-PV", "Não"),       # PT's own wins; PCdoB, PV take the federation's
        ("y", "PT", ""), ("y", "Bl PlFdrPtUniPp...", "Não"),        # empty passes down to the bloc
        ("z", "PmdbPpPtbPscPhsPen", "Sim"), ("z", "PpPtbPsc", "Não"),  # two blocs disagree for PP, PTB, PSC
    ], columns=["votacao_id", "bancada", "orientacao"])
    a = o.applicable(t).set_index(["votacao_id", "party"]).orientacao
    assert a[("x", "PT")] == "Sim" and a[("x", "PCDOB")] == "Não"
    assert a[("y", "PT")] == "Não" and a[("y", "PL")] == "Não"
    assert ("z", "PP") not in a.index and a[("z", "MDB")] == "Sim"


def test_orientations_table(built):
    t = read(built, "orientations", "2025-03")
    assert t.columns.tolist() == ["votacao_id", "bancada", "orientacao"]
    assert t.votacao_id.unique().tolist() == ["v1", "v2", "v3"]   # v4 committee and v999 unknown dropped
    assert len(t[(t.votacao_id == "v1") & (t.bancada == "P1")]) == 1
    assert t[(t.votacao_id == "v2") & (t.bancada == "P1")].orientacao.tolist() == [""]
    assert read(built, "orientations", "2025-04").bancada.tolist() == ["P1"]


def test_votes_carry_the_party_at_vote_time(built):
    v = read(built, "votes", "2025-03")
    assert v[v.deputado_id == "20"].partido.tolist() == ["A", "B", "B"]


def test_discipline(built):
    d = o.discipline("2025-03", data_dir=built).set_index("deputado_id")
    cols = ["n_votes", "n_party", "n_with_party", "n_free", "n_none", "n_unknown", "n_gov", "n_with_gov"]
    assert d.loc[10, cols].tolist() == [2, 2, 2, 0, 0, 0, 2, 2]
    assert d.loc[20, cols].tolist() == [2, 1, 0, 1, 0, 0, 2, 2]   # against A in v1, freed by B in v2
    assert d.loc[30, cols].tolist() == [2, 2, 0, 0, 0, 0, 2, 0]   # v2: P1 gave none, the federation said Não
    assert d.loc[40, cols].tolist() == [2, 2, 0, 0, 0, 0, 2, 0]   # obstruction counts as a Não
    assert 100 not in d.index                                   # abstained and Artigo 17: no votes
    assert d.loc[20, "with_party"] == 0 and d.loc[10, "with_gov"] == 1
    assert d.loc[20, "partido"] == "B"                          # display: latest label that month

    apr = o.discipline("2025-04", data_dir=built).set_index("deputado_id")
    assert apr.loc[10, ["n_none", "n_unknown"]].tolist() == [1, 0]   # P1 listed, gave none
    assert apr.loc[20, ["n_none", "n_unknown"]].tolist() == [0, 1]   # C is in no bancada
    assert math.isnan(apr.loc[10, "with_party"])


def test_discipline_obstruction_not_as_no(built):
    d = o.discipline("2025-03", obstruction_as_no=False, data_dir=built).set_index("deputado_id")
    assert d.loc[40, "n_votes"] == 1   # v1's obstruction is not a vote


def test_index_columns(built):
    from politicaleye.camara import summary

    row = summary.month_row("2025-03", built)
    assert row["orientation_coverage"] == 1.0
    assert row["oriented_share"] == round(7 / 8, 4)
    assert row["with_party"] == round(2 / 7, 4)     # 10: 2/2, 20: 0/1, 30: 0/2, 40: 0/2
    assert row["with_gov"] == round(4 / 8, 4)
    apr = summary.month_row("2025-04", built)
    assert apr["orientation_coverage"] == 0.5 and apr["oriented_share"] == 0.0
    assert apr["with_party"] is None                # nobody had a line to follow
