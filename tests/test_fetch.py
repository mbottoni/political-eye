"""The downloader against a local server that drops connections like the real one."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from camaragraphs.fetch import fetch


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


def test_resumes_after_drops(server, tmp_path):
    body = bytes(range(256)) * 4000
    setup(body, drops=3)
    src = fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    assert (tmp_path / "votacoes-2025.csv").read_bytes() == body
    assert src.size == len(body) and src.etag == '"v1"'


def test_file_changing_mid_download_restarts_cleanly(server, tmp_path):
    old, new = b"a" * 30000, b"b" * 45000
    setup(old, drops=1, swap=(new, '"v2"'))
    src = fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    # never a splice of the two versions
    assert (tmp_path / "votacoes-2025.csv").read_bytes() == new
    assert src.etag == '"v2"' and src.size == len(new)


def test_cache_hit_skips_download(server, tmp_path):
    setup(b"x" * 1000, drops=0)
    fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    (tmp_path / "votacoes-2025.csv").write_bytes(b"y" * 1000)  # same size, marker content
    fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    assert (tmp_path / "votacoes-2025.csv").read_bytes() == b"y" * 1000


def test_missing_year_returns_none(server, tmp_path):
    setup(b"", drops=0)
    assert fetch("missing", 2031, tmp_path, base_url=server, backoff=0) is None


def test_stale_partial_from_an_older_version_is_not_spliced(server, tmp_path):
    import json
    # A previous run died part-way through version v1 ...
    (tmp_path / "votacoes-2025.csv.part").write_bytes(b"a" * 1000)
    (tmp_path / "votacoes-2025.part.json").write_text(json.dumps({
        "dataset": "votacoes", "year": 2025, "url": "", "size": 3000, "etag": '"v1"', "last_modified": "",
    }))
    # ... and the server has since moved to v2.
    setup(b"b" * 2500, drops=0, etag='"v2"')
    src = fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    assert (tmp_path / "votacoes-2025.csv").read_bytes() == b"b" * 2500
    assert src.etag == '"v2"'
    assert not (tmp_path / "votacoes-2025.part.json").exists()


def test_partial_without_provenance_is_discarded(server, tmp_path):
    (tmp_path / "votacoes-2025.csv.part").write_bytes(b"a" * 1000)
    setup(b"b" * 2500, drops=0)
    fetch("votacoes", 2025, tmp_path, base_url=server, backoff=0)
    assert (tmp_path / "votacoes-2025.csv").read_bytes() == b"b" * 2500
