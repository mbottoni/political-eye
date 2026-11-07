"""Monthly co-voting and co-authorship graphs of Brazil's Senado Federal.

Data in ``data/senado/``; every default is explained in ``methodology/senado.md``.
"""

from .graphs import (
    LOP,
    MAX_AUTHORS,
    MIN_ITEMS,
    MIN_SHARED,
    TAU,
    Month,
    aligned,
    cosponsor_edges,
    covote_edges,
    graph,
    legislatura,
    load_month,
    months,
    series,
    vote_matrix,
)

__all__ = [
    "LOP", "MAX_AUTHORS", "MIN_ITEMS", "MIN_SHARED", "TAU", "Month", "aligned", "cosponsor_edges",
    "covote_edges", "graph", "legislatura", "load_month", "months", "series", "vote_matrix",
]
