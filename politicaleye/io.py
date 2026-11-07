"""Reading raw files and writing the committed tables, the same way for every source.

Committed CSVs are written sorted by the caller, without an index, with
``\\n`` line endings: a rebuild that changes nothing produces no git diff.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def read_raw(path: Path, usecols: list[str] | None = None, *, sep: str = ";",
             encoding: str = "utf-8-sig") -> pd.DataFrame:
    """A raw government CSV, every column as text, empty fields kept as ``""``."""
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False, encoding=encoding, usecols=usecols)


def write_csv(df: pd.DataFrame, path: Path, **kw) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", **kw)


def write_sources(path: Path, records: dict[str, dict]) -> None:
    """Merge provenance records into ``sources.json``, keyed and sorted by name."""
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(old.items())), indent=2, ensure_ascii=False) + "\n")
