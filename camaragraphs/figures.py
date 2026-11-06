"""The README chart, in light and dark. CI re-renders it after every update.

Output is byte-deterministic (no timestamps, bundled font, explicit PCA
signs), so an unchanged month never produces a commit.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from . import graphs as g

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", muted="#898781", PT="#e34948", PL="#2a78d6",
                  other="#c3c2b7", edge="#0b0b0b"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", muted="#898781", PT="#e66767", PL="#3987e5",
                 other="#5c5b57", edge="#f0efec"),
}
EMPHASIS = ("PT", "PL")   # the two poles of the current house; everyone else is context
FULL_MONTH = 30           # contested roll calls needed for a month to be pictured


def _mpl(theme: str):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = THEMES[theme]
    plt.rcdefaults()
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "figure.facecolor": t["surface"], "axes.facecolor": t["surface"], "savefig.facecolor": t["surface"],
        "text.color": t["ink"], "axes.titlelocation": "left", "axes.titlesize": 10, "axes.titlecolor": t["ink"],
        "legend.frameon": False, "legend.labelcolor": t["ink"],
    })
    return plt, t


def _save(fig, path: Path) -> None:
    import matplotlib.pyplot as plt

    fig.savefig(path, metadata={"Software": None}, bbox_inches="tight", pad_inches=0.15, dpi=200)
    plt.close(fig)


# ------------------------------------------------------------------- layout

def _pca2(M: np.ndarray) -> np.ndarray:
    """First two principal components of a +1/-1/0 vote matrix (0 = missing)."""
    X = M.astype(float)
    seen = M != 0
    mean = (X * seen).sum(0) / np.maximum(seen.sum(0), 1)
    X = np.where(seen, X - mean, 0.0)
    U, S, _ = np.linalg.svd(X, full_matrices=False)
    P = U[:, :2] * S[:2]
    # SVD signs differ between BLAS builds: pin them so output is identical
    # everywhere. Scores sum to zero, so use the sign of the third moment
    # (order-free), falling back to the largest entry when that is ~0.
    for k in range(P.shape[1]):
        skew = float((P[:, k] ** 3).sum())
        ref = skew if abs(skew) > 1e-9 else P[np.argmax(np.abs(P[:, k])), k]
        if ref < 0:
            P[:, k] *= -1
    return P


def _positions(month: str, nodes: list[int], data_dir, **kw) -> np.ndarray:
    ids, _, M = g.vote_matrix(g.load_month(month, data_dir).votes,
                              **{k: v for k, v in kw.items() if k in ("lop", "obstruction_as_no")})
    row = {d: i for i, d in enumerate(ids)}
    P = _pca2(M[[row[n] for n in nodes]])
    if P.shape[1] < 2:
        P = np.column_stack([P, np.zeros((len(P), 2 - P.shape[1]))])
    return P


def _orient(P: np.ndarray, parties: list[str]) -> np.ndarray:
    """Government left, opposition right: put PT on the left when present."""
    pt = np.array([p == "PT" for p in parties])
    if pt.any() and P[pt, 0].mean() > 0:
        P = P * np.array([-1, 1])
    return P


# ------------------------------------------------------------------ network

def network(month: str, path: Path, theme: str, data_dir=None, **kw) -> None:
    plt, t = _mpl(theme)
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    gv, gc = g.aligned(month, data_dir=data_dir, **kw)
    nodes = list(gv.nodes)
    parties = [gv.nodes[n].get("party", "") for n in nodes]
    P = _orient(_positions(month, nodes, data_dir, **kw), parties) if nodes else np.zeros((0, 2))
    xy = {n: P[i] for i, n in enumerate(nodes)}
    group = np.array([p if p in EMPHASIS else "other" for p in parties])

    # Stacked, not side by side: the vote map is a wide arc, so full-width
    # panels spend the space on deputies instead of on blank margins.
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.6), gridspec_kw={"hspace": 0.12})
    panels = [(axes[0], gv, "Vote together", 0.006), (axes[1], gc, "Sign together", 0.05)]
    for ax, G, title, alpha in panels:
        segs = [(xy[u], xy[v]) for u, v in G.edges]
        ax.add_collection(LineCollection(segs, colors=t["edge"], linewidths=0.3, alpha=alpha, zorder=1))
        for z, key in enumerate(("other", *EMPHASIS[::-1]), start=2):
            sel = group == key
            ax.scatter(P[sel, 0], P[sel, 1], s=20, c=t[key], edgecolors=t["surface"], linewidths=0.6, zorder=z)
        ax.set_title(f"{title}: {G.number_of_edges():,} edges")
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        # Direct labels just outside each pole's outermost deputy, so they
        # never cover the dots they name.
        for p in EMPHASIS:
            sel = group == p
            if not sel.any():
                continue
            left = P[sel, 0].mean() < P[:, 0].mean()
            i = np.argmin(P[sel, 0]) if left else np.argmax(P[sel, 0])
            ax.annotate(p, (P[sel, 0][i], P[sel, 1].mean()), xytext=(-10 if left else 10, 0),
                        textcoords="offset points", ha="right" if left else "left", va="center",
                        fontsize=11, fontweight="bold", color=t["ink"], zorder=10)
    counts = Counter(group)
    handles = [Line2D([], [], ls="", marker="o", ms=7, mfc=t[k], mec=t["surface"],
                      label=f"{k if k != 'other' else 'Other parties'} ({counts.get(k, 0)})")
               for k in (*EMPHASIS, "other")]
    fig.legend(handles=handles, loc="upper right", ncol=3, bbox_to_anchor=(1.0, 0.98), handletextpad=0.3)
    fig.text(0.0, 0.03,
             f"{month}: {len(nodes)} deputies active in both graphs. Each dot is a deputy, placed by the first two "
             f"principal components of that month's roll-call votes; positions are identical in both panels.",
             fontsize=8, color=t["muted"], ha="left")
    _save(fig, path)


# -------------------------------------------------------------------- entry

def pictured_month(idx: pd.DataFrame, full_month: int = FULL_MONTH) -> str | None:
    full = idx[idx.votacoes_contested >= full_month]
    return full.month.iloc[-1] if len(full) else None


def render(data_dir: Path, out_dir: Path, *, full_month: int = FULL_MONTH, **kw) -> str | None:
    """Write the network chart for both themes; return the month pictured."""
    idx = pd.read_csv(data_dir / "index.csv", dtype={"month": str})
    out_dir.mkdir(parents=True, exist_ok=True)
    month = pictured_month(idx, full_month)
    if month:
        for theme in THEMES:
            network(month, out_dir / f"network-{theme}.png", theme, data_dir=data_dir, **kw)
    return month
