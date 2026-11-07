"""TSE's candidate and campaign-finance files for the general elections.

Two zips per election from TSE's CDN, regenerated as accounts are filed and
judged: ``consulta_cand_<year>.zip`` (candidates) and
``prestacao_de_contas_eleitorais_candidatos_<year>.zip`` (revenues, expenses
contracted and paid; 300 MB to 500 MB). Each holds a ``*_BRASIL.csv`` with
the whole country plus one file per state, which are not used.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from ..fetch import download_zip

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
GENERAL = (2018, 2022, 2026)   # general elections covered (federal and state offices)


def files(year: int) -> dict[str, str]:
    return {
        f"consulta_cand_{year}": f"{CDN}/consulta_cand/consulta_cand_{year}.zip",
        f"prestacao_de_contas_eleitorais_candidatos_{year}":
            f"{CDN}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{year}.zip",
    }


def fetch(year: int, raw: Path) -> dict[str, dict]:
    out = {}
    for name, url in files(year).items():
        p = download_zip(url, raw / f"{name}.zip", attempts=8, timeout=300)
        if p is None:
            raise RuntimeError(f"{url}: 404")
        out[name] = asdict(p)
    return out
