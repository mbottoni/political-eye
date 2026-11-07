"""The Câmara's yearly bulk CSV files.

The server drops long transfers part-way, so a plain GET of a 90 MB file
fails often enough to break a scheduled job; :func:`politicaleye.fetch.download`
resumes them safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..fetch import download, log

BASE_URL = "https://dadosabertos.camara.leg.br/arquivos"
DATASETS = ("votacoes", "votacoesVotos", "votacoesOrientacoes", "proposicoes", "proposicoesAutores")


@dataclass
class Source:
    dataset: str
    year: int
    url: str
    size: int
    etag: str
    last_modified: str


def url_for(dataset: str, year: int, base_url: str = BASE_URL) -> str:
    return f"{base_url}/{dataset}/csv/{dataset}-{year}.csv"


def fetch(dataset: str, year: int, cache_dir: Path, *, base_url: str = BASE_URL, **kw) -> Source | None:
    """Download one bulk file into ``cache_dir``; return its provenance.

    ``None`` when the file does not exist (404), which happens for a year
    that has not started yet. ``kw`` goes to :func:`politicaleye.fetch.download`.
    """
    url = url_for(dataset, year, base_url)
    p = download(url, cache_dir / f"{dataset}-{year}.csv", **kw)
    if p is None:
        log(f"{dataset}-{year}: not published (404), skipping")
        return None
    return Source(dataset, year, url, p.size, p.etag, p.last_modified)


def fetch_years(years: list[int], cache_dir: Path, **kw) -> list[Source]:
    """Fetch every dataset for each year. A year missing any dataset is skipped."""
    out = []
    for year in years:
        got = [fetch(d, year, cache_dir, **kw) for d in DATASETS]
        if any(s is None for s in got):
            log(f"{year}: incomplete on the server, not building it")
            continue
        out.extend(got)
    return out
