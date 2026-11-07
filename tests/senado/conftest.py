"""A tiny fake year of Senado API responses, in the real format."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from politicaleye.senado import graphs
from politicaleye.senado.build import build_year

NAMES = {"1": "Ana", "2": "Bia", "3": "Caio", "4": "Davi", "5": "Eva"}
PARTY = {"1": "PT", "2": "PT", "3": "PL", "4": "PL", "5": "MDB"}


def voto(code, v, party=None, uf="SP"):
    return {"codigoParlamentar": int(code), "descricaoVotoParlamentar": None, "nomeParlamentar": NAMES[code],
            "sexoParlamentar": "F", "siglaPartidoParlamentar": PARTY[code] if party is None else party,
            "siglaUFParlamentar": uf, "siglaVotoParlamentar": v}


def votacao(vid, day, votos, *, secret=False, informe=None, totals=(None, None, None), sigla="PL", sessao=100, seq=None):
    return {
        "ano": 2025, "casaSessao": "SF", "codigoMateria": 1, "codigoSessao": sessao, "codigoSessaoVotacao": vid,
        "dataSessao": day, "descricaoVotacao": f"Votação  nominal\n{vid}", "idProcesso": 900 + vid,
        "identificacao": f"{sigla} {vid}/2025", "sigla": sigla, "siglaTipoSessao": "DOR",
        "resultadoVotacao": "A", "votacaoSecreta": "S" if secret else "N", "sequencialVotacao": seq,
        "totalVotosSim": totals[0], "totalVotosNao": totals[1], "totalVotosAbstencao": totals[2],
        "informeLegislativo": {"data": informe or day, "texto": "..."}, "votos": votos,
    }


def senadores(codes):
    return {"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
        {"IdentificacaoParlamentar": {"CodigoParlamentar": c, "NomeParlamentar": NAMES[c],
                                      "SiglaPartidoParlamentar": "XX", "UfParlamentar": "SP"}}
        for c in codes]}}}


def processo(pid, ident, day, autoria, casa="SF", objetivo=None):
    return {"autoria": autoria, "casaIdentificadora": casa, "codigoMateria": pid, "dataApresentacao": day,
            "id": pid, "identificacao": ident, "objetivo": objetivo, "situacaoAtual": "TRAMITANDO", "tramitando": "Sim"}


def write_raw_2025(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    S, N = "Sim", "Não"
    votes = [
        votacao(11, "2025-03-11", [voto("1", S), voto("2", S), voto("3", N), voto("4", N), voto("5", "P-NRV")], seq=4011),
        votacao(12, "2025-03-12", [voto("1", S), voto("2", N), voto("3", N), voto("4", N), voto("5", S),
                                   voto("5", S)], seq=4012),                          # duplicate row
        votacao(13, "2025-03-12", [voto(c, "Votou") for c in "1234"], secret=True, totals=(3, 1, 0), sessao=99),
        votacao(14, "2025-03-13", None),                                               # no individual votes
        votacao(15, "2025-03-13", [voto("1", S)], informe="1998-11-04"),             # misdated 1998 vote
        votacao(16, "2025-04-01", [voto("1", S), voto("3", N, party="S/Partido"), voto("4", "AP", party="")]),
        votacao(17, "2024-12-30", [voto("1", S)]),                                     # wrong year
    ]
    (raw / "votacao-2025.json").write_text(json.dumps(votes, ensure_ascii=False))

    def ori(seq, given):
        return {"sequencialVotacao": seq, "orientacoesLideranca": [
            {"dataHora": f"2025-03-11T18:{i:02d}:00", "partido": p, "voto": v} for i, (p, v) in enumerate(given)]}
    (raw / "orientacao-2025.json").write_text(json.dumps({"votacoes": [
        ori(4011, [("PT", "SIM"), ("PL", "NÃO"), ("Governo", "SIM"), ("MDB", "SIM"), ("MDB", "LIVRE")]),  # MDB changed its mind
        ori(4012, [("PT", "SIM"), ("Progressistas", "SIM"), ("Governo", "NÃO")]),
        ori(9999, [("PT", "NÃO")]),                     # a roll call /votacao does not list
        {"sequencialVotacao": 4013, "orientacoesLideranca": []},
    ]}, ensure_ascii=False))
    (raw / "senadores-57.json").write_text(json.dumps(senadores(["1", "2", "3", "4", "5"]), ensure_ascii=False))
    by = {
        "1": [processo(501, "PL 1/2025", "2025-03-05", "Senadora Ana (PT/SP), Senadora Bia (PT/SP), Senador Caio (PL/SP)"),
              processo(503, "RQS 3/2025", "2025-04-02", "Líder do PT Ana (PT/SP)"),
              processo(504, "PEC 4/2025", "2025-03-20", "Senadora Ana (PT/SP), Senador Davi (PL/SP), e outros")],
        "2": [processo(501, "PL 1/2025", "2025-03-05", "Senadora Ana (PT/SP), Senadora Bia (PT/SP), Senador Caio (PL/SP)")],
        "3": [processo(501, "PL 1/2025", "2025-03-05", "Senadora Ana (PT/SP), Senadora Bia (PT/SP), Senador Caio (PL/SP)"),
              processo(505, "PL 5/2024", "2024-12-31", "Senador Caio (PL/SP)"),        # wrong year
              processo(506, "VET 6/2025", "2025-03-21", "Presidência da República", casa="CN"),
              processo(507, "PL 7/2025", "2025-03-22", "Câmara dos Deputados", objetivo="Revisora")],
        "4": [processo(504, "PEC 4/2025", "2025-03-20", "Senadora Ana (PT/SP), Senador Davi (PL/SP), e outros"),
              processo(506, "VET 6/2025", "2025-03-21", "Presidência da República", casa="CN")],
        "5": [processo(504, "PEC 4/2025", "2025-03-20", "Senadora Ana (PT/SP), Senador Davi (PL/SP), e outros")],
    }
    for code, items in by.items():
        p = raw / "autoria" / "2025" / f"{code}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(items, ensure_ascii=False))


@pytest.fixture
def built(tmp_path: Path) -> Path:
    raw, data = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)
    build_year(2025, raw, data)
    graphs._load.cache_clear()
    yield data
    graphs._load.cache_clear()
