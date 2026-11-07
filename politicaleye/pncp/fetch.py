"""The Portal Nacional de Contratações Públicas' consultation API.

``https://pncp.gov.br/api/consulta/v1/contratos`` (by publication date) and
``/v1/contratos/atualizacao`` (by last update), 500 contracts a page, dates
as ``yyyyMMdd``. No data is HTTP 204 with an empty body. Past about 20
requests a minute the API answers 429 with an HTML page and no
``Retry-After``; it clears within a minute. So requests are paced and a 429
waits it out.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ..fetch import NETWORK_ERRORS, USER_AGENT, log

API = "https://pncp.gov.br/api/consulta/v1"
PAUSE = 4.0          # seconds between requests (about 15 a minute)
WAIT_429 = 75.0
PAGE = 500
_last = [0.0]


def _get(url: str, attempts: int = 8) -> dict | None:
    for attempt in range(1, attempts + 1):
        wait = PAUSE - (time.monotonic() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
                status = r.status
            _last[0] = time.monotonic()
            if status == 204 or not body.strip():
                return None
            return json.loads(body)
        except urllib.error.HTTPError as e:
            _last[0] = time.monotonic()
            if e.code == 429:
                log(f"pncp: 429, waiting {WAIT_429:.0f}s")
                time.sleep(WAIT_429)
                continue
            if e.code < 500:
                raise
            err: Exception = e
        except (*NETWORK_ERRORS, json.JSONDecodeError) as e:
            _last[0] = time.monotonic()
            err = e
        time.sleep(min(10 * attempt, 60))
    raise RuntimeError(f"GET {url} failed {attempts} times: {err}")


def contratos(day: str, *, updated: bool = False, api: str = API) -> list[dict]:
    """Every contract published (or, with ``updated``, changed) on ``day`` (``YYYY-MM-DD``)."""
    d = day.replace("-", "")
    base = f"{api}/contratos{'/atualizacao' if updated else ''}?dataInicial={d}&dataFinal={d}&tamanhoPagina={PAGE}"
    out, page, total = [], 1, None
    while True:
        doc = _get(f"{base}&pagina={page}")
        if doc is None:
            break
        out.extend(doc.get("data") or [])
        total = doc.get("totalRegistros", total)
        if not doc.get("paginasRestantes"):
            break
        page += 1
    if total is not None and len(out) != total:
        raise RuntimeError(f"{day}: {len(out)} contracts read, the API reports {total}")
    return out
