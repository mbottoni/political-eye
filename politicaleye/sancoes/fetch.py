"""The federal sanctions lists, as the Portal da Transparência publishes them.

Each list is one zip of the day's snapshot, and only the latest snapshot can
be downloaded (older dates answer 403), so the history exists only if someone
records it. Each list's download page names its current date in its script
(``arquivos.push({"ano" : "2026", "mes" : "11", "dia" : "06", ...})``).
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from ..fetch import download_zip, get_bytes, log

PAGE = "https://portaldatransparencia.gov.br/download-de-dados/{ds}"
FILE = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/{ds}/{date}_{name}.zip"
DATASETS = {   # download name -> file name
    "ceis": "CEIS",                          # companies and people barred from public contracts
    "cnep": "CNEP",                          # companies punished under the Anti-Corruption Law
    "cepim": "CEPIM",                        # non-profits barred from federal agreements
    "acordos-leniencia": "AcordosLeniencia",  # leniency agreements
}
DATE = re.compile(rb'arquivos\.push\(\{\s*"ano"\s*:\s*"(\d{4})"\s*,\s*"mes"\s*:\s*"(\d{2})"\s*,\s*"dia"\s*:\s*"(\d{2})"')


def latest_date(ds: str) -> str:
    """``YYYYMMDD`` of the snapshot the download page offers."""
    page = get_bytes(PAGE.format(ds=ds), attempts=4, timeout=60)
    dates = sorted(b"".join(m) for m in DATE.findall(page or b""))
    if not dates:
        raise RuntimeError(f"{ds}: no date on the download page")
    return dates[-1].decode()


def fetch(raw: Path) -> dict[str, dict]:
    """Download every list's current snapshot; return provenance by list, with its ``date``."""
    out = {}
    for ds, name in DATASETS.items():
        date = latest_date(ds)
        url = FILE.format(ds=ds, date=date, name=name)
        p = download_zip(url, raw / f"{ds}.zip", attempts=8, timeout=120)
        if p is None:
            raise RuntimeError(f"{url}: 404")
        out[ds] = {**asdict(p), "date": f"{date[:4]}-{date[4:6]}-{date[6:]}"}
        log(f"{ds}: snapshot of {out[ds]['date']}")
    return out
