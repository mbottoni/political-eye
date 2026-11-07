"""The Câmara's parliamentary blocs and federations, recorded as they change.

The blocs API (``/api/v2/blocos``) lists the blocs of each legislature with
their member parties, but with no dates, and it stops listing a bloc once it
is dissolved: the 2023-2024 bloc behind ``Bl UniPpFdrPsdbCid...`` is gone.
A daily job records what the API lists. ``data/camara/blocos/`` keeps:

- ``blocos.csv``: ``bloco_id, legislatura, nome, federacao, listed_from,
  listed_until``;
- ``members.csv``: ``bloco_id, partido, listed_from, listed_until``.

``listed_from`` is the first daily snapshot that listed the row, and
``listed_until`` the first that no longer did (empty while still listed).
Rows already listed on :data:`RECORDING_STARTED` may be older than that.
``orientations.py`` uses the record to complete bloc names that the vote
files cut off (``Bl UniPpPsd...``). ``methodology/camara.md`` has the rules.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..fetch import get_json, log
from ..io import write_csv

API = "https://dadosabertos.camara.leg.br/api/v2"
RECORDING_STARTED = "2026-11-07"
FIRST_LEGISLATURA = 55   # 2015-2019, the first year of data/camara

BLOCOS_COLS = ["bloco_id", "legislatura", "nome", "federacao", "listed_from", "listed_until"]
MEMBERS_COLS = ["bloco_id", "partido", "listed_from", "listed_until"]


def current_legislatura(today: dt.date) -> int:
    """Legislature in force on ``today`` (each starts on 1 February)."""
    return (today.year - (1 if today.month == 1 else 0) - 1795) // 4


def _get(url: str) -> list[dict]:
    doc = get_json(url)
    if doc is None or "dados" not in doc:
        raise RuntimeError(f"{url}: no data")
    return doc["dados"]


def snapshot(legislaturas: list[int], api: str = API) -> tuple[pd.DataFrame, pd.DataFrame]:
    """What the API lists right now: ``(blocos, members)`` without dates.

    A bloc's members come from ``/blocos/{id}/partidos``; when that is empty
    (it is for some blocs), from the parties its name lists.
    """
    blocos, members = [], []
    for leg in legislaturas:
        rows = _get(f"{api}/blocos?idLegislatura={leg}&itens=100")
        if not rows:
            raise RuntimeError(f"legislatura {leg}: the API lists no blocs, refusing to record that")
        for b in rows:
            bid = int(b["id"])
            blocos.append((bid, int(b["idLegislatura"]), b["nome"].strip(), int(bool(b["federacao"]))))
            parts = [p["sigla"].strip() for p in _get(f"{api}/blocos/{bid}/partidos")]
            members.extend((bid, p) for p in parts)
    bl = pd.DataFrame(blocos, columns=BLOCOS_COLS[:4]).drop_duplicates()
    mem = pd.DataFrame(members, columns=MEMBERS_COLS[:2]).drop_duplicates()

    # Members named only in the bloc's name. A federation in a name is
    # written by its own name ("Federação PSDB CIDADANIA"), so look it up.
    fed = {(r.legislatura, r.nome): mem[mem.bloco_id == r.bloco_id].partido.tolist()
           for r in bl[bl.federacao == 1].itertuples()}
    extra = []
    for r in bl[~bl.bloco_id.isin(mem.bloco_id)].itertuples():
        for e in name_elements(r.nome):
            extra.extend((r.bloco_id, p) for p in fed.get((r.legislatura, e), [e] if not e.startswith("Federação") else []))
    mem = pd.concat([mem, pd.DataFrame(extra, columns=MEMBERS_COLS[:2])]).drop_duplicates()
    return bl, mem


def name_elements(nome: str) -> list[str]:
    """The comma-separated parties and federations of an API bloc name."""
    return [e.strip() for e in nome.split(",") if e.strip()]


def _merge(old: pd.DataFrame, now: pd.DataFrame, key: list[str], today: str, cols: list[str]) -> pd.DataFrame:
    """Close rows no longer listed, open rows newly listed, keep the rest."""
    def keys(df: pd.DataFrame) -> list[tuple]:
        return list(df[key].astype(str).itertuples(index=False, name=None))

    old = old.copy()
    listed = set(keys(now))
    is_open = (old.listed_until == "").to_numpy()
    k_old = keys(old)
    old.loc[[o and k not in listed for o, k in zip(is_open, k_old)], "listed_until"] = today
    still = {k for o, k in zip(is_open, k_old) if o and k in listed}
    new = now[[k not in still for k in keys(now)]].assign(listed_from=today, listed_until="")
    return pd.concat([old, new], ignore_index=True)[cols]


def _read(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(path, dtype=str, keep_default_na=False)[cols]


def update(data: Path, today: dt.date | None = None, *, api: str = API) -> dict:
    """Record today's API listing in ``data/blocos/``. Returns what changed."""
    today = today or dt.datetime.now(dt.UTC).date()
    legs = list(range(FIRST_LEGISLATURA, current_legislatura(today) + 1))
    bl, mem = snapshot(legs, api)
    d = data / "blocos"
    old_bl, old_mem = _read(d / "blocos.csv", BLOCOS_COLS), _read(d / "members.csv", MEMBERS_COLS)
    day = today.isoformat()
    bl = bl.astype(str)
    mem = mem.astype(str)
    new_bl = _merge(old_bl, bl, ["bloco_id", "legislatura", "nome", "federacao"], day, BLOCOS_COLS)
    new_mem = _merge(old_mem, mem, ["bloco_id", "partido"], day, MEMBERS_COLS)

    def order(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
        return df.assign(_id=df.bloco_id.astype(int)).sort_values(["_id", *by]).drop(columns="_id")

    d.mkdir(parents=True, exist_ok=True)
    write_csv(order(new_bl, ["listed_from", "nome"]), d / "blocos.csv")
    write_csv(order(new_mem, ["partido", "listed_from"]), d / "members.csv")
    def closed(df: pd.DataFrame) -> int:
        return int((df.listed_until == day).sum())

    changes = {
        "blocos_listed": len(new_bl) - len(old_bl), "blocos_unlisted": closed(new_bl) - closed(old_bl),
        "members_listed": len(new_mem) - len(old_mem), "members_unlisted": closed(new_mem) - closed(old_mem),
    }
    log(f"blocos: {len(bl)} listed in legislaturas {legs[0]}-{legs[-1]}; {changes}")
    load.cache_clear()
    return changes


# ------------------------------------------------------------------- reading

@lru_cache(maxsize=8)
def load(root: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``(blocos, members)`` from a data directory or raw URL; empty if not recorded."""
    out = []
    for name, cols in (("blocos", BLOCOS_COLS), ("members", MEMBERS_COLS)):
        src = f"{root}/blocos/{name}.csv" if isinstance(root, str) else root / "blocos" / f"{name}.csv"
        try:
            out.append(pd.read_csv(src, dtype=str, keep_default_na=False)[cols])
        except (FileNotFoundError, OSError, ValueError):
            out.append(pd.DataFrame(columns=cols))
    return out[0], out[1]


def in_effect(df: pd.DataFrame, day: str, *, before_recording: bool = False) -> pd.DataFrame:
    """Rows certainly listed for the whole of ``day`` (a Brasília date).

    The snapshot runs before dawn in Brasília. A row first listed on day D
    joined during D-1 or overnight, so it counts from D. A row first missing
    on day D left during D-1 or overnight, so it counts until D-2. With
    ``before_recording``, rows already listed when recording started also
    count for any earlier day.
    """
    start = df.listed_from
    if before_recording:
        start = start.mask(start == RECORDING_STARTED, "")
    last = pd.to_datetime(df.listed_until.replace("", None), format="%Y-%m-%d") - pd.Timedelta(days=2)
    last = last.dt.strftime("%Y-%m-%d").fillna("9999-12-31")
    return df[(start <= day) & (day <= last)]
