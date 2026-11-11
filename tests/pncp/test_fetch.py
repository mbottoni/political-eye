import io
import urllib.error

import pytest

from politicaleye.pncp import fetch


def _raise(code, body):
    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "", {}, io.BytesIO(body))
    return urlopen


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)


def test_missing_page_is_a_runtime_error(monkeypatch):
    calls = []
    body = b'{"message":"P\xc3\xa1gina 17 inexistente.","status":"400"}'
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda req, timeout=None: calls.append(1) or _raise(400, body)(req))
    with pytest.raises(RuntimeError, match="HTTP 400 Página 17 inexistente"):
        fetch._get("https://pncp.example/contratos?pagina=17")
    assert len(calls) == 1                     # not retried: the day is left for the next run


def test_422_is_retried_then_a_runtime_error(monkeypatch):
    calls = []
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda req, timeout=None: calls.append(1) or _raise(422, b"")(req))
    with pytest.raises(RuntimeError, match="failed 3 times: HTTP 422"):
        fetch._get("https://pncp.example/contratos?pagina=1", attempts=3)
    assert len(calls) == 3
