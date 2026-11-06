"""A tiny fake year of Câmara bulk files, in the real on-disk format."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from camaragraphs import graphs
from camaragraphs.build import build_year


def _raw(path: Path, header: list[str], rows: list[list[str]]) -> None:
    # Real files: UTF-8 with BOM, ';'-separated, every field quoted.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


VOTACOES = ["id", "data", "dataHoraRegistro", "siglaOrgao", "aprovacao", "votosSim", "votosNao", "votosOutros", "descricao"]
VOTOS = ["idVotacao", "dataHoraVoto", "voto", "deputado_id", "deputado_nome", "deputado_siglaPartido", "deputado_siglaUf"]
PROPS = ["id", "siglaTipo", "dataApresentacao"]
AUTORES = ["idProposicao", "idDeputadoAutor", "nomeAutor", "siglaPartidoAutor", "siglaUFAutor", "ordemAssinatura", "proponente"]

NAMES = {"10": "Ana", "20": "Bia", "30": "Caio", "40": "Davi", "100": "Eva"}


def vote(vid, t, voto, dep, party="P1"):
    return [vid, t, voto, dep, NAMES[dep], party, "SP"]


def author(pid, dep, order="1"):
    return [pid, dep, NAMES.get(dep, "Senado"), "P1", "SP", order, "1"]


def write_raw_2025(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    _raw(raw / "votacoes-2025.csv", VOTACOES, [
        ["v1", "2025-03-10", "2025-03-10T15:00:00", "PLEN", "1", "2", "2", "1", "Primeira; com \"aspas\"\ne quebra"],
        ["v2", "2025-03-11", "2025-03-11T15:00:00", "PLEN", "0", "2", "2", "1", "Segunda"],
        ["v3", "2025-03-12", "2025-03-12T15:00:00", "PLEN", "1", "4", "0", "0", "Unânime"],
        ["v4", "2025-03-12", "2025-03-12T16:00:00", "CCJC", "1", "1", "0", "0", "Comissão"],
        ["v5", "2025-04-01", "2025-04-01T15:00:00", "PLEN", "1", "1", "1", "0", "Abril"],
        ["v6", "2024-12-30", "2024-12-30T15:00:00", "PLEN", "1", "1", "0", "0", "Ano errado"],
        ["v7", "2025-03-13", "2025-03-13T15:00:00", "PLEN", "1", "0", "0", "0", "Simbólica"],
    ])
    _raw(raw / "votacoesVotos-2025.csv", VOTOS, [
        vote("v1", "2025-03-10T15:01:00", "Sim", "10"),
        vote("v1", "2025-03-10T15:09:00", "Sim", "10"),  # duplicate
        vote("v1", "2025-03-10T15:01:00", "Sim", "20", party="A"),
        vote("v1", "2025-03-10T15:01:00", "Não", "30"),
        vote("v1", "2025-03-10T15:01:00", "Obstrução", "40"),
        vote("v1", "2025-03-10T15:01:00", "Abstenção", "100"),
        vote("v2", "2025-03-11T15:01:00", "Não", "10"),
        vote("v2", "2025-03-11T15:01:00", "Não", "20", party="B"),  # switched party
        vote("v2", "2025-03-11T15:01:00", "Sim", "30"),
        vote("v2", "2025-03-11T15:01:00", "Sim", "40"),
        vote("v2", "2025-03-11T15:01:00", "Artigo 17", "100"),
        *[vote("v3", "2025-03-12T15:01:00", "Sim", d, party="B" if d == "20" else "P1") for d in ("10", "20", "30", "40")],
        vote("v4", "2025-03-12T16:01:00", "Sim", "10"),
        vote("v5", "2025-04-01T15:01:00", "Sim", "10"),
        vote("v5", "2025-04-01T15:01:00", "Não", "20"),
        vote("v6", "2024-12-30T15:01:00", "Sim", "10"),
    ])
    _raw(raw / "proposicoes-2025.csv", PROPS, [
        ["1", "PL", "2025-03-05T10:00:00"],
        ["2", "REQ", "2025-03-06T10:00:00"],
        ["3", "PL", "2025-03-07T10:00:00"],
        ["4", "PEC", "2025-03-08T10:00:00"],
        ["5", "PL", "2024-12-31T10:00:00"],
    ])
    _raw(raw / "proposicoesAutores-2025.csv", AUTORES, [
        author("1", "10", "1"), author("1", "20", "2"), author("1", "30", "3"),
        author("2", "10"), author("2", "20", "2"),
        author("3", "40"),
        *[author("4", d, str(i)) for i, d in enumerate(("10", "20", "30", "40", "100"), 1)],
        author("5", "10"),
        author("1", ""),        # a senator: no deputy id
        author("999", "10"),    # proposição missing from proposicoes-2025
    ])


@pytest.fixture
def built(tmp_path: Path) -> Path:
    raw, data = tmp_path / "raw", tmp_path / "data"
    write_raw_2025(raw)
    build_year(2025, raw, data)
    graphs._load.cache_clear()
    yield data
    graphs._load.cache_clear()
