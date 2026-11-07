"""Where the repo keeps things. Each source owns ``data/<source>/``."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
