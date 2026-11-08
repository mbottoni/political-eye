"""The Senado's open-data API, one year at a time.

Per year ``Y`` the raw cache (``.cache/raw/senado/``) holds:

- ``votacao-Y.json``: ``/votacao?dataInicio=Y-01-01&dataFim=Y-12-31``, every
  Plenário roll call with each senator's vote (the API's limit is one year
  per call);
- ``senadores-L.json``: ``/senador/lista/legislatura/L?exercicio=S``, everyone
  who took office in legislature ``L``, for the legislatures ``Y`` touches;
- ``autoria/Y/<code>.json``: ``/processo?codigoParlamentarAutor=<code>`` for
  ``Y``, every matéria each of those senators signed. The by-date listing
  names authors only as text, so co-authors are found from each senator's
  side;
- ``orientacao-Y.json``: ``/plenario/votacao/orientacaoBancada/Y0101/Y1231``,
  how party and government leaders oriented each roll call (from October
  2018).

The API asks clients to stay under 10 requests a second; this stays near 4.
Endpoints marked deprecated in the API's OpenAPI document are not used.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ..fetch import get_bytes, log

API = "https://legis.senado.leg.br/dadosabertos"
PAUSE = 0.25   # seconds between requests
FIRST_YEAR = 2015
FIRST_ORIENTATION_YEAR = 2018


def legislaturas(year: int) -> list[int]:
    """The legislatures in force during ``year`` (January belongs to the previous one)."""
    first = (year - 1 - 1795) // 4
    last = (year - 1795) // 4
    return sorted({first, last})


def _get(url: str, dest: Path) -> dict:
    """Download ``url`` (JSON) to ``dest``; return its provenance."""
    time.sleep(PAUSE)
    body = get_bytes(url, headers={"Accept": "application/json"}, attempts=6, timeout=120,
                     check=lambda b: json.loads(b))
    if body is None:
        raise RuntimeError(f"{url}: 404")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return {"url": url, "size": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def votacao_url(year: int, api: str = API) -> str:
    return f"{api}/votacao?dataInicio={year}-01-01&dataFim={year}-12-31"


def senadores_url(leg: int, api: str = API) -> str:
    return f"{api}/senador/lista/legislatura/{leg}.json?exercicio=S"


def autoria_url(code: str, year: int, api: str = API) -> str:
    return (f"{api}/processo?codigoParlamentarAutor={code}"
            f"&dataInicioApresentacao={year}-01-01&dataFimApresentacao={year}-12-31")


def orientacao_url(year: int, api: str = API) -> str:
    return f"{api}/plenario/votacao/orientacaoBancada/{year}0101/{year}1231"


def _listed_uf(p: dict, leg: int) -> str:
    """A listed senator's UF: from the mandate covering ``leg``, else the identification, else any mandate.

    The identification block carries ``UfParlamentar`` only for senators in
    office now (21 of 145 in the 54th legislature's list); every mandate has it.
    """
    ms = (p.get("Mandatos") or {}).get("Mandato") or []
    ms = ms if isinstance(ms, list) else [ms]
    covers = lambda m: str(leg) in {str((m.get(k) or {}).get("NumeroLegislatura", "")) for k in ("PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato")}
    for uf in [m.get("UfParlamentar") for m in ms if covers(m)] + [p["IdentificacaoParlamentar"].get("UfParlamentar")] + [m.get("UfParlamentar") for m in ms]:
        if (uf or "").strip():
            return uf.strip()
    return ""


def senators_listed(raw: Path, legs: list[int]) -> list[dict]:
    """Everyone in the cached legislature lists: ``{codigo, nome, uf}``, by code."""
    out = {}
    for leg in legs:
        doc = json.loads((raw / f"senadores-{leg}.json").read_text())
        rows = doc["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"]
        for p in rows if isinstance(rows, list) else [rows]:
            i = p["IdentificacaoParlamentar"]
            out[i["CodigoParlamentar"]] = {"codigo": i["CodigoParlamentar"], "nome": i["NomeParlamentar"].strip(), "uf": _listed_uf(p, leg)}
    return [out[k] for k in sorted(out, key=int)]


def fetch_year(year: int, raw: Path, *, api: str = API) -> dict[str, dict]:
    """Download everything ``year`` is built from. Returns provenance records by name."""
    records = {}
    records[f"votacao-{year}"] = _get(votacao_url(year, api), raw / f"votacao-{year}.json")
    if year >= FIRST_ORIENTATION_YEAR:
        records[f"orientacao-{year}"] = _get(orientacao_url(year, api), raw / f"orientacao-{year}.json")
    legs = legislaturas(year)
    for leg in legs:
        records[f"senadores-{leg}"] = _get(senadores_url(leg, api), raw / f"senadores-{leg}.json")
    people = senators_listed(raw, legs)
    digest, size = hashlib.sha256(), 0
    for i, p in enumerate(people, 1):
        r = _get(autoria_url(p["codigo"], year, api), raw / "autoria" / str(year) / f"{p['codigo']}.json")
        digest.update(f"{p['codigo']}:{r['sha256']}\n".encode())
        size += r["size"]
        if i % 50 == 0:
            log(f"senado {year}: authorship of {i}/{len(people)} senators")
    records[f"autoria-{year}"] = {"url": autoria_url("<code>", year, api), "files": len(people), "size": size,
                                  "sha256": digest.hexdigest()}
    log(f"senado {year}: {len(people)} senators, {records[f'votacao-{year}']['size']} bytes of votes")
    return records
