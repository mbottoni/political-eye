"""The Portal da Transparência's parliamentary amendments file.

One zip, regenerated every night (about 03:00 UTC), with every amendment
since 2014 and three CSVs (latin-1, ``;``-separated):

- ``EmendasParlamentares.csv``: each amendment by place and budget line,
  with what has been committed (empenhado), settled (liquidado) and paid;
- ``EmendasParlamentares_PorFavorecido.csv``: who received the money, month
  by month;
- ``EmendasParlamentares_Convenios.csv``: the agreements (convênios) that
  carry it.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from ..fetch import download_zip

URL = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/emendas-parlamentares/EmendasParlamentares.zip"
FILES = {
    "emendas": "EmendasParlamentares.csv",
    "favorecidos": "EmendasParlamentares_PorFavorecido.csv",
    "convenios": "EmendasParlamentares_Convenios.csv",
}


def fetch(raw: Path, url: str = URL) -> dict:
    """Download the zip into ``raw``; return its provenance."""
    p = download_zip(url, raw / "EmendasParlamentares.zip", attempts=8, timeout=120)
    if p is None:
        raise RuntimeError(f"{url}: 404")
    return asdict(p)
