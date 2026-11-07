"""Downloads that survive flaky government servers. Shared by every source.

- Large files resume with ``Range`` requests guarded by ``If-Range``, so a
  resumed transfer can never splice two versions of a file. (The Câmara's
  server drops long transfers part-way: HTTP/2 stream resets, truncated
  HTTP/1.1 bodies.)
- A file whose ETag and size have not changed is not downloaded again.
- Zips are CRC-checked: a server that regenerates a file in place can serve a
  truncated copy whose Content-Length matches (seen at B3).
- Some servers answer 404 for a file that exists; ``retry_404`` re-asks, and
  a previously verified local copy is kept if the server still says 404.

Every download returns its :class:`Provenance`, which a source records in its
``data/<source>/sources.json``.
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

USER_AGENT = "political-eye (+https://github.com/mbottoni/political-eye)"
CHUNK = 1 << 20
NETWORK_ERRORS = (urllib.error.URLError, http.client.HTTPException, OSError)


@dataclass
class Provenance:
    """Which version of a file was used. ``size`` is -1 when the server sent no length."""

    url: str
    size: int
    etag: str
    last_modified: str


def log(msg: str) -> None:
    print(f"[fetch] {msg}", file=sys.stderr)


def _req(url: str, method: str = "GET", headers: dict | None = None, user_agent: str = USER_AGENT):
    return urllib.request.Request(url, method=method, headers={"User-Agent": user_agent, **(headers or {})})


def _provenance(url: str, r) -> Provenance:
    return Provenance(url, int(r.headers.get("Content-Length") or -1), r.headers.get("ETag", ""),
                      r.headers.get("Last-Modified", ""))


def _sleep(backoff: float, attempt: int) -> None:
    time.sleep(min(backoff**attempt, 30))


def get_json(url: str, *, attempts: int = 4, timeout: float = 30, backoff: float = 2.0,
             user_agent: str = USER_AGENT):
    """GET a small JSON document with retries. Returns ``None`` on 404."""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(_req(url, user_agent=user_agent), timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err: Exception = e
        except (*NETWORK_ERRORS, json.JSONDecodeError) as e:
            err = e
        if attempt < attempts:
            _sleep(backoff, attempt)
    raise RuntimeError(f"GET {url} failed {attempts} times: {err}")


def download(url: str, dest: Path, *, attempts: int = 8, timeout: float = 60, backoff: float = 2.0,
             retry_404: int = 0, wait_404: float = 20, user_agent: str = USER_AGENT) -> Provenance | None:
    """Download ``url`` to ``dest``. ``None`` if the server says the file does not exist.

    Sidecars next to ``dest``: ``<name>.json`` (provenance of the completed
    file), ``<name>.part`` and ``<name>.part.json`` (an interrupted transfer
    and the version it belongs to).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta = dest.with_name(dest.name + ".json")
    part = dest.with_name(dest.name + ".part")
    pmeta = dest.with_name(dest.name + ".part.json")

    head, misses = None, 0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(_req(url, "HEAD", user_agent=user_agent), timeout=timeout) as r:
                head = _provenance(url, r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                if misses < retry_404:
                    misses += 1
                    log(f"{dest.name}: 404, asking again ({misses}/{retry_404}) in {wait_404:.0f}s")
                    time.sleep(wait_404)
                    continue
                if dest.exists() and meta.exists():
                    log(f"{dest.name}: server says 404; keeping the verified local copy")
                    return Provenance(**json.loads(meta.read_text()))
                return None
            err: Exception = e
        except NETWORK_ERRORS as e:
            err = e
        log(f"{dest.name}: HEAD failed ({err}); retry {attempt}/{attempts}")
        _sleep(backoff, attempt)
    if head is None:
        raise RuntimeError(f"HEAD {url} failed {attempts} times")

    if dest.exists() and meta.exists() and head.size >= 0 and dest.stat().st_size == head.size:
        if Provenance(**json.loads(meta.read_text())) == head:
            log(f"{dest.name}: cached ({head.size:,} bytes)")
            return head

    # Bytes already in .part are reusable only if we know which version of the
    # file they belong to; resuming then asks for *that* version (If-Range).
    src = head
    if part.exists() and pmeta.exists():
        src = Provenance(**json.loads(pmeta.read_text()))
    else:
        part.write_bytes(b"")
    for attempt in range(1, attempts + 1):
        have = part.stat().st_size
        if src.size >= 0 and have == src.size:
            break
        if src.size >= 0 and have > src.size:
            part.write_bytes(b"")
            have = 0
        # If-Range: the server sends the remaining bytes only if the file is
        # still the version we started; otherwise it sends all of it (200).
        headers = {"Range": f"bytes={have}-", "If-Range": src.etag or src.last_modified} if have else {}
        try:
            with urllib.request.urlopen(_req(url, headers=headers, user_agent=user_agent), timeout=timeout) as r:
                if r.status == 200:
                    # A fresh start, or the file changed under us: adopt the
                    # version actually being sent.
                    src = _provenance(url, r)
                    pmeta.write_text(json.dumps(asdict(src)))
                    mode = "wb"
                elif r.status == 206:
                    mode = "ab"
                else:
                    raise RuntimeError(f"unexpected HTTP {r.status} for {url}")
                with part.open(mode) as f:
                    while chunk := r.read(CHUNK):
                        f.write(chunk)
            if src.size < 0:      # no Content-Length: a clean EOF is the end
                break
        except urllib.error.HTTPError as e:
            if e.code == 416 and part.stat().st_size == src.size:
                break
            log(f"{dest.name}: HTTP {e.code}; restarting from zero")
            part.write_bytes(b"")
            _sleep(backoff, attempt)
        except NETWORK_ERRORS as e:
            log(f"{dest.name}: dropped at {part.stat().st_size:,}/{src.size:,} bytes ({e.__class__.__name__}); "
                f"resuming {attempt}/{attempts}")
            _sleep(backoff, attempt)
    else:
        raise RuntimeError(f"GET {url} did not complete after {attempts} attempts")

    if src.size >= 0 and part.stat().st_size != src.size:
        raise RuntimeError(f"{url}: got {part.stat().st_size} bytes, expected {src.size}")
    part.replace(dest)
    pmeta.unlink(missing_ok=True)
    meta.write_text(json.dumps(asdict(src)))
    log(f"{dest.name}: downloaded {dest.stat().st_size:,} bytes")
    return src


def zip_ok(path: Path) -> bool:
    """A complete, CRC-clean zip. Size checks alone miss a truncated copy
    served while the file is being regenerated."""
    try:
        with zipfile.ZipFile(path) as z:
            return z.testzip() is None
    except (zipfile.BadZipFile, OSError, EOFError):
        return False


def download_zip(url: str, dest: Path, *, tries: int = 4, wait: float = 60, **kw) -> Provenance | None:
    """:func:`download` plus an integrity check; a corrupt zip is discarded
    and fetched again after ``wait`` seconds."""
    for attempt in range(1, tries + 1):
        src = download(url, dest, **kw)
        if src is None or zip_ok(dest):
            return src
        log(f"{dest.name}: corrupt zip (server mid-update?); retry {attempt}/{tries} in {wait:.0f}s")
        for p in (dest, dest.with_name(dest.name + ".json")):
            p.unlink(missing_ok=True)
        if attempt < tries:
            time.sleep(wait)
    raise RuntimeError(f"{url}: still corrupt after {tries} downloads")
