"""Load every explorer page (and tab) in headless Chrome against this checkout's data.

Fails if a page shows an error box, an unfilled tile, or no content at all.
Run: python tests/pages_smoke.py (needs Chrome; CI's Ubuntu runners have it).
"""

from __future__ import annotations

import functools
import http.server
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [
    "docs/index.html",
    "docs/camara/", "docs/camara/?tab=network", "docs/camara/?tab=ideal",
    "docs/senado/", "docs/senado/?tab=network", "docs/senado/?tab=ideal", "docs/senado/?tab=discipline",
    *[f"docs/orientacoes/?tab={t}" for t in ("gov", "cohesion", "rebels", "orient", "deputy", "blocs")],
]
CHROME = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def chrome() -> str:
    for c in CHROME:
        if shutil.which(c) or Path(c).exists():
            return c
    sys.exit("no Chrome found")


def main() -> int:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

    handler = functools.partial(Quiet, directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port, bad = srv.server_address[1], 0
    for page in PAGES:
        out = subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=60000",
                              "--dump-dom", f"http://localhost:{port}/{page}"], capture_output=True, text=True, timeout=180).stdout
        out = re.sub(r"<script.*?</script>", "", out, flags=re.S)   # the page's code mentions its own error texts
        problems = [m[:120] for m in re.findall(r"Could not load[^<]*", out)]
        problems += [f"tile {m}" for m in re.findall(r'class="value"[^>]*>–<', out)]
        if len(out) < 2000:
            problems.append("almost empty page")
        status = "ok" if not problems else "; ".join(problems[:3])
        bad += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {page}  {status if problems else ''}")
    srv.shutdown()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
