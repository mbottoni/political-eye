"""scripts/size_report.py runs on a small repository and counts what it should."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("size_report", ROOT / "scripts" / "size_report.py")
size_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(size_report)


def test_source_of():
    assert size_report.source_of("data/pncp/contratos/2026-10.csv") == "pncp"
    assert size_report.source_of("data/site/pncp/resumo.json") == "site"
    assert size_report.source_of("data/README.md") == "data"
    assert size_report.source_of("politicaleye/io.py") == "code"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, check=True, capture_output=True)


def test_report_on_a_small_repository(tmp_path, capsys):
    _git(tmp_path, "init", "-q")
    (tmp_path / "data/pncp").mkdir(parents=True)
    (tmp_path / "data/site/pncp").mkdir(parents=True)
    (tmp_path / "data/pncp/a.csv").write_text("x\n" * 1000)
    (tmp_path / "data/site/pncp/resumo.json").write_text(json.dumps(
        {"coverage": {"days_read": 10, "span_days": 40, "first": "2026-01-01", "last": "2026-01-10", "since": "2025-12-02"}}))
    (tmp_path / "run.py").write_text("print(1)\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "one")
    (tmp_path / "data/pncp/a.csv").write_text("y\n" * 2000)
    _git(tmp_path, "commit", "-q", "-am", "two")

    size_report.main(tmp_path)
    out = capsys.readouterr().out
    assert "Working tree" in out and "History" in out and "Growth" in out
    pncp = next(line for line in out.splitlines() if line.strip().startswith("pncp ") and "a.csv" in line)
    assert pncp.split()[1] == "1"                       # one tracked file
    assert re.search(r"data/pncp/a\.csv\s+2\s", out)    # two versions in history
    assert "10 of 40 days read (25.0%)" in out
    assert "siconfi: coverage unavailable" in out       # no Siconfi summary here, and no crash
