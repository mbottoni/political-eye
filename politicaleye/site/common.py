"""Helpers shared by the page summaries: deterministic JSON and CSV under ``data/site/``."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from ..io import write_csv
from ..paths import DATA

SITE = DATA / "site"


def clean(x, digits: int = 4):
    """JSON-safe, rounded, NaN -> None, numpy -> Python, recursively."""
    if isinstance(x, dict):
        return {str(k): clean(v, digits) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)):
        return [clean(v, digits) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        x = x.item()
    if isinstance(x, float):
        return None if math.isnan(x) or math.isinf(x) else round(x, digits)
    return x


def write_json(obj, path: Path, digits: int = 4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj, digits), ensure_ascii=False, separators=(",", ":")) + "\n")


def records(df: pd.DataFrame, digits: int = 4) -> dict:
    """A frame as compact columns: {"columns": [...], "rows": [[...], ...]}."""
    return {"columns": list(df.columns), "rows": clean(df.astype(object).where(df.notna(), None).values.tolist(), digits)}


def csv(df: pd.DataFrame, path: Path) -> None:
    write_csv(df, path)
