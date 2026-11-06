"""Download the Câmara's yearly bulk CSV files.

The server drops long transfers part-way (HTTP/2 stream resets, truncated
HTTP/1.1 bodies), so a plain GET of a 90 MB file fails often enough to break a
scheduled job. Downloads here resume with ``Range`` requests guarded by
``If-Range``, so a resumed transfer can never splice two versions of a file.
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_URL = "https://dadosabertos.camara.leg.br/arquivos"
DATASETS = ("votacoes", "votacoesVotos", "proposicoes", "proposicoesAutores")
USER_AGENT = "camara-graphs (+https://github.com/mbottoni/camara-graphs)"
CHUNK = 1 << 20


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


def _log(msg: str) -> None:
    print(f"[fetch] {msg}", file=sys.stderr)


def _request(url: str, method: str = "GET", headers: dict | None = None):
    h = {"User-Agent": USER_AGENT, **(headers or {})}
    return urllib.request.Request(url, method=method, headers=h)


def _head(url: str, timeout: float) -> tuple[int, str, str]:
    with urllib.request.urlopen(_request(url, "HEAD"), timeout=timeout) as r:
        return int(r.headers["Content-Length"]), r.headers.get("ETag", ""), r.headers.get("Last-Modified", "")


def fetch(
    dataset: str,
    year: int,
    cache_dir: Path,
    *,
    attempts: int = 8,
    timeout: float = 60,
    base_url: str = BASE_URL,
    backoff: float = 2.0,
) -> Source | None:
    """Download one bulk file into ``cache_dir``; return its provenance.

    Returns ``None`` when the file does not exist (404), which happens for a
    year that has not started yet. Reuses the cached copy when the server's
    ETag and size match what was downloaded last time.
    """
    url = url_for(dataset, year, base_url)
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{dataset}-{year}.csv"
    meta = cache_dir / f"{dataset}-{year}.json"
    part = cache_dir / f"{dataset}-{year}.csv.part"

    for attempt in range(1, attempts + 1):
        try:
            size, etag, modified = _head(url, timeout)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                _log(f"{dataset}-{year}: not published (404), skipping")
                return None
            err: Exception = e
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            err = e
        _log(f"{dataset}-{year}: HEAD failed ({err}); retry {attempt}/{attempts}")
        time.sleep(min(backoff**attempt, 30))
    else:
        raise RuntimeError(f"HEAD {url} failed {attempts} times")

    src = Source(dataset, year, url, size, etag, modified)
    if dest.exists() and meta.exists() and dest.stat().st_size == size:
        if json.loads(meta.read_text()) == asdict(src):
            _log(f"{dataset}-{year}: cached ({size:,} bytes)")
            return src

    # Bytes already in .part are reusable only if we know which version of the
    # file they belong to; resuming then asks for *that* version (If-Range).
    pmeta = cache_dir / f"{dataset}-{year}.part.json"
    if part.exists() and pmeta.exists():
        src = Source(**json.loads(pmeta.read_text()))
    else:
        part.write_bytes(b"")
    for attempt in range(1, attempts + 1):
        have = part.stat().st_size
        if have == src.size:
            break
        if have > src.size:
            part.write_bytes(b"")
            have = 0
        headers = {}
        if have:
            # If-Range: the server sends the remaining bytes only if the file
            # is still the version we started; otherwise it sends all of it.
            headers = {"Range": f"bytes={have}-", "If-Range": src.etag or src.last_modified}
        try:
            with urllib.request.urlopen(_request(url, headers=headers), timeout=timeout) as r:
                if r.status == 200:
                    # Full body: either a fresh start or the file changed
                    # under us. Adopt the version actually being sent.
                    src = Source(dataset, year, url, int(r.headers["Content-Length"]),
                                 r.headers.get("ETag", ""), r.headers.get("Last-Modified", ""))
                    pmeta.write_text(json.dumps(asdict(src)))
                    mode = "wb"
                elif r.status == 206:
                    mode = "ab"
                else:
                    raise RuntimeError(f"unexpected HTTP {r.status} for {url}")
                with part.open(mode) as f:
                    while chunk := r.read(CHUNK):
                        f.write(chunk)
        except urllib.error.HTTPError as e:
            if e.code == 416 and part.stat().st_size == src.size:
                break
            _log(f"{dataset}-{year}: HTTP {e.code}; restarting from zero")
            part.write_bytes(b"")
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            got = part.stat().st_size
            _log(f"{dataset}-{year}: dropped at {got:,}/{src.size:,} bytes ({e.__class__.__name__}); "
                 f"resuming {attempt}/{attempts}")
            time.sleep(min(backoff**attempt, 30))
    else:
        raise RuntimeError(f"GET {url} did not complete after {attempts} attempts")

    if part.stat().st_size != src.size:
        raise RuntimeError(f"{url}: got {part.stat().st_size} bytes, expected {src.size}")
    part.replace(dest)
    pmeta.unlink(missing_ok=True)
    meta.write_text(json.dumps(asdict(src)))
    _log(f"{dataset}-{year}: downloaded {src.size:,} bytes")
    return src


def fetch_years(years: list[int], cache_dir: Path, **kw) -> list[Source]:
    """Fetch every dataset for each year. A year missing any dataset is skipped."""
    out = []
    for year in years:
        got = [fetch(d, year, cache_dir, **kw) for d in DATASETS]
        if any(s is None for s in got):
            _log(f"{year}: incomplete on the server, not building it")
            continue
        out.extend(got)
    return out
