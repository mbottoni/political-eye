"""Per-month summary: ``data/senado/index.csv``.

Each row describes the graphs for the window ending at that month
(``window_start`` to ``month``), so every count is over the window.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import graphs as core
from . import graphs as g


def month_row(month: str, data_dir: Path) -> dict:
    w = g.WINDOW
    d = g.load_window(month, w, data_dir)
    _, kept, _ = g.vote_matrix(d.votes)
    nv, ev = g._covote(month, window=w, min_shared=g.MIN_SHARED, lop=g.LOP, data_dir=data_dir)
    nc, ec = g._cosponsor(month, window=w, max_authors=g.MAX_AUTHORS, types=None, exclude=g.EXCLUDE_TYPES,
                          data_dir=data_dir)
    ev_on = ev[ev.agreement >= g.TAU]
    ec_on = ec[ec.n_items >= g.MIN_ITEMS]
    au = d.authorship[~d.authorship.sigla_tipo.isin(list(g.EXCLUDE_TYPES))]
    k = au.groupby(g.ITEM).size()
    return {
        "month": month,
        "legislatura": g.legislatura(month),
        "window_start": g.window_months(month, w)[0],
        "votacoes": len(d.votacoes),
        "votacoes_secret": int((d.votacoes.secreta == "1").sum()) if len(d.votacoes) else 0,
        "votacoes_contested": len(kept),
        "covote_nodes": len(nv),
        "covote_edges": len(ev_on),
        "covote_density": core.density(len(nv), len(ev_on)),
        "mean_agreement": round(float(ev.agreement.mean()), 4) if len(ev) else None,
        "items_signed": int(k.size),
        "items_cosigned": int(((k >= 2) & (k <= g.MAX_AUTHORS)).sum()),
        "items_signature_drive": int((k > g.MAX_AUTHORS).sum()),
        "cosponsor_nodes": len(nc),
        "cosponsor_edges": len(ec_on),
        "cosponsor_density": core.density(len(nc), len(ec_on)),
        "aligned_nodes": len(set(nv.tolist()) & set(nc.tolist())),
    }


def build_index(data_dir: Path) -> pd.DataFrame:
    df = pd.DataFrame([month_row(m, data_dir) for m in g.months(data_dir)])
    df.to_csv(data_dir / "index.csv", index=False, lineterminator="\n")
    return df
