"""The Tesouro Nacional's Siconfi API: municipalities' fiscal reports.

``https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`` (Oracle REST). The
API allows one request a second and answers one municipality and period per
call, so a full history is tens of thousands of calls; see ``build.py`` for
how the work is spread over runs.

Wrong or missing parameters do not fail: they return an empty list, which
is indistinguishable from "this municipality did not report".
"""

from __future__ import annotations

import json
import time

from ..fetch import get_json

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
PAUSE = 1.05   # seconds between requests: the API's limit is one a second
_last = [0.0]


def _get(url: str) -> dict:
    wait = PAUSE - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    try:
        doc = get_json(url, attempts=6, timeout=120, backoff=3.0)
    finally:
        _last[0] = time.monotonic()
    if doc is None:
        raise RuntimeError(f"{url}: 404")
    return doc


def _all(url: str) -> list[dict]:
    """Every item, following ``hasMore`` with our own offsets (the API's links point to an internal host)."""
    out, offset = [], 0
    while True:
        doc = _get(f"{url}&offset={offset}&limit=5000" if "?" in url else f"{url}?offset={offset}&limit=5000")
        items = doc.get("items") or []
        out.extend(items)
        if not doc.get("hasMore") or not items:
            return out
        offset += len(items)


def entes(api: str = API) -> list[dict]:
    return _all(f"{api}/entes")


def rgf(ibge: str, ano: int, periodicidade: str, periodo: int, *, api: str = API) -> list[dict]:
    """Every annex of the Executive's RGF for one municipality and period (one call)."""
    tipo = "RGF" if periodicidade == "Q" else "RGF%20Simplificado"
    return _all(f"{api}/rgf?an_exercicio={ano}&in_periodicidade={periodicidade}&nr_periodo={periodo}"
                f"&co_tipo_demonstrativo={tipo}&co_poder=E&id_ente={ibge}")


def dumps(items: list[dict]) -> bytes:
    return json.dumps(items, ensure_ascii=False, sort_keys=True).encode()
