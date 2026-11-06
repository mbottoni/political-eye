"""Per-month summary: ``data/index.csv``."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import graphs as g


def month_row(month: str, data_dir: Path) -> dict:
    d = g.load_month(month, data_dir)
    _, kept, _ = g.vote_matrix(d.votes)
    nv, ev = g._covote(month, min_shared=g.MIN_SHARED, lop=g.LOP, obstruction_as_no=True, data_dir=data_dir)
    nc, ec = g._cosponsor(month, max_authors=g.MAX_AUTHORS, types=None, exclude=g.EXCLUDE_TYPES, data_dir=data_dir)
    ev_on = ev[ev.agreement >= g.TAU]
    ec_on = ec[ec.n_items >= g.MIN_ITEMS]
    au = d.authorship[~d.authorship.sigla_tipo.isin(list(g.EXCLUDE_TYPES))]
    k = au.groupby("proposicao_id").size()

    def density(n_nodes: int, n_edges: int) -> float:
        return round(2 * n_edges / (n_nodes * (n_nodes - 1)), 4) if n_nodes > 1 else 0.0

    # Every pair in ev shares >= MIN_SHARED votes, so both ends are covote
    # nodes: the mean is over the same population the density is computed on.
    return {
        "month": month,
        "legislatura": g.legislatura(month),
        "votacoes": len(d.votacoes),
        "votacoes_contested": len(kept),
        "covote_nodes": len(nv),
        "covote_edges": len(ev_on),
        "covote_density": density(len(nv), len(ev_on)),
        "mean_agreement": round(float(ev.agreement.mean()), 4) if len(ev) else None,
        "items_signed": int(k.size),
        "items_cosigned": int(((k >= 2) & (k <= g.MAX_AUTHORS)).sum()),
        "items_signature_drive": int((k > g.MAX_AUTHORS).sum()),
        "cosponsor_nodes": len(nc),
        "cosponsor_edges": len(ec_on),
        "cosponsor_density": density(len(nc), len(ec_on)),
        "aligned_nodes": len(set(nv.tolist()) & set(nc.tolist())),
    }


def build_index(data_dir: Path) -> pd.DataFrame:
    df = pd.DataFrame([month_row(m, data_dir) for m in g.months(data_dir)])
    df.to_csv(data_dir / "index.csv", index=False, lineterminator="\n")
    return df
