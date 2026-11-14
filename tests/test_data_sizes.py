"""No committed table may approach GitHub's 100 MB per-file limit: a push with one is refused whole."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT_MB = 90


def test_no_data_file_near_githubs_limit():
    try:
        files = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        files = [str(p.relative_to(ROOT)) for p in (ROOT / "data").rglob("*") if p.is_file()]
    big = {f: round((ROOT / f).stat().st_size / 1e6, 1) for f in files if (ROOT / f).exists() and (ROOT / f).stat().st_size > LIMIT_MB * 1e6}
    assert not big, f"files over {LIMIT_MB} MB (split them, like data/pncp/contratos/): {big}"
