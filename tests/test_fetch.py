"""The shared downloader against a local server that drops connections like the Câmara's."""

import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from politicaleye.camara.fetch import fetch
from politicaleye.fetch import download, download_zip, zip_ok


class Flaky(BaseHTTPRequestHandler):
    body = b""
    etag = '"v1"'
    drops = 0
    swap_after_drop: tuple[bytes, str] | None = None

    def log_message(self, *a):
        pass

    def _headers(self, status, length, extra=()):
        self.send_response(status)
        self.send_header("Content-Length", str(length))
        self.send_header("ETag", Flaky.etag)
        self.send_header("Last-Modified", "Thu, 05 Nov 2026 07:00:00 GMT")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def do_HEAD(self):
        if "missing" in self.path:
            self.send_error(404)
            return
        self._headers(200, len(Flaky.body))

    def do_GET(self):
        start, status, extra = 0, 200, []
        rng = self.headers.get("Range")
        if rng and self.headers.get("If-Range") == Flaky.etag:
            start = int(rng.removeprefix("bytes=").removesuffix("-"))
            status = 206
            extra = [("Content-Range", f"bytes {start}-{len(Flaky.body) - 1}/{len(Flaky.body)}")]
        data = Flaky.body[start:]
        self._headers(status, len(data), extra)
        if Flaky.drops > 0:
            Flaky.drops -= 1
            self.wfile.write(data[: len(data) // 3])
            self.wfile.flush()
            self.close_connection = True
            if Flaky.swap_after_drop:
                Flaky.body, Flaky.etag = Flaky.swap_after_drop
                Flaky.swap_after_drop = None
            return
        self.wfile.write(data)


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Flaky)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def setup(body: bytes, drops: int, etag='"v1"', swap=None):
    Flaky.body, Flaky.etag, Flaky.drops, Flaky.swap_after_drop = body, etag, drops, swap


def get(server, tmp_path, **kw):
    return download(f"{server}/f.csv", tmp_path / "f.csv", backoff=0, **kw)


def test_resumes_after_drops(server, tmp_path):
    body = bytes(range(256)) * 4000
    setup(body, drops=3)
    src = get(server, tmp_path)
    assert (tmp_path / "f.csv").read_bytes() == body
    assert src.size == len(body) and src.etag == '"v1"'


def test_file_changing_mid_download_restarts_cleanly(server, tmp_path):
    old, new = b"a" * 30000, b"b" * 45000
    setup(old, drops=1, swap=(new, '"v2"'))
    src = get(server, tmp_path)
    # never a splice of the two versions
    assert (tmp_path / "f.csv").read_bytes() == new
    assert src.etag == '"v2"' and src.size == len(new)


def test_cache_hit_skips_download(server, tmp_path):
    setup(b"x" * 1000, drops=0)
    get(server, tmp_path)
    (tmp_path / "f.csv").write_bytes(b"y" * 1000)  # same size, marker content
    get(server, tmp_path)
    assert (tmp_path / "f.csv").read_bytes() == b"y" * 1000


def test_missing_file_returns_none(server, tmp_path):
    setup(b"", drops=0)
    assert download(f"{server}/missing.csv", tmp_path / "m.csv", backoff=0) is None


def test_404_keeps_a_verified_local_copy(server, tmp_path):
    setup(b"x" * 1000, drops=0)
    first = download(f"{server}/missing.csv", tmp_path / "m.csv", backoff=0)
    assert first is None
    (tmp_path / "m.csv").write_bytes(b"x" * 10)
    (tmp_path / "m.csv.json").write_text(json.dumps({"url": "u", "size": 10, "etag": '"v1"', "last_modified": ""}))
    kept = download(f"{server}/missing.csv", tmp_path / "m.csv", backoff=0, retry_404=1, wait_404=0)
    assert kept.size == 10 and (tmp_path / "m.csv").read_bytes() == b"x" * 10


def test_stale_partial_from_an_older_version_is_not_spliced(server, tmp_path):
    # A previous run died part-way through version v1 ...
    (tmp_path / "f.csv.part").write_bytes(b"a" * 1000)
    (tmp_path / "f.csv.part.json").write_text(json.dumps({
        "url": "", "size": 3000, "etag": '"v1"', "last_modified": "",
    }))
    # ... and the server has since moved to v2.
    setup(b"b" * 2500, drops=0, etag='"v2"')
    src = get(server, tmp_path)
    assert (tmp_path / "f.csv").read_bytes() == b"b" * 2500
    assert src.etag == '"v2"'
    assert not (tmp_path / "f.csv.part.json").exists()


def test_partial_without_provenance_is_discarded(server, tmp_path):
    (tmp_path / "f.csv.part").write_bytes(b"a" * 1000)
    setup(b"b" * 2500, drops=0)
    get(server, tmp_path)
    assert (tmp_path / "f.csv").read_bytes() == b"b" * 2500


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_zip_integrity(tmp_path):
    good = _zip({"a.csv": b"x;y\n" * 5000})
    (tmp_path / "good.zip").write_bytes(good)
    (tmp_path / "cut.zip").write_bytes(good[: len(good) // 2])
    assert zip_ok(tmp_path / "good.zip") and not zip_ok(tmp_path / "cut.zip")


def test_download_zip_refetches_a_corrupt_copy(server, tmp_path, monkeypatch):
    import politicaleye.fetch as f

    good = _zip({"a.csv": b"x;y\n" * 5000})
    # A truncated copy whose Content-Length matches, as B3 serves mid-rewrite.
    setup(good[: len(good) // 2], drops=0, etag='"cut"')
    real = f.download

    def download_then_server_finishes(*a, **kw):
        src = real(*a, **kw)
        setup(good, drops=0, etag='"good"')
        return src

    monkeypatch.setattr(f, "download", download_then_server_finishes)
    src = download_zip(f"{server}/z.zip", tmp_path / "z.zip", wait=0, backoff=0)
    assert src.etag == '"good"' and zip_ok(tmp_path / "z.zip")


# The Câmara layer on top: provenance per dataset and year.

def test_camara_fetch_records_dataset_and_year(server, tmp_path):
    setup(b"x" * 500, drops=0)
    src = fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    assert (src.dataset, src.year, src.size, src.etag) == ("votacoes", 2025, 500, '"v1"')
    assert src.url == f"{server}/votacoes/csv/votacoes-2025.csv"
    assert (tmp_path / "votacoes-2025.csv").read_bytes() == b"x" * 500


def test_camara_fetch_missing_year_returns_none(server, tmp_path):
    setup(b"", drops=0)
    assert fetch("missing", 2031, tmp_path, base_url=server, backoff=0) is None
