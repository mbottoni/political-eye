"""The README's charts, in light and dark. CI re-renders them after every update.

Output is byte-deterministic (fixed SVG hash salt, no timestamps, bundled
font, explicit PCA signs), so an unchanged month never produces a commit.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from . import graphs as g

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
                  axis="#c3c2b7", line="#2a78d6", PT="#e34948", PL="#2a78d6", other="#c3c2b7", edge="#0b0b0b"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
                 axis="#383835", line="#3987e5", PT="#e66767", PL="#3987e5", other="#5c5b57", edge="#f0efec"),
}
# One-hue sequential ramp (blue 100 -> 700). Dark mode runs it the other way,
# so "near zero" recedes into the surface in both themes.
RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
        "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
EMPHASIS = ("PT", "PL")   # the two poles of the current house; everyone else is context
FULL_MONTH = 30           # contested roll calls needed for a month to be pictured
THIN = 10                 # below this, a month is a gap in the timeline (= MIN_SHARED: no edge is possible)
EVENTS = [("2016-04", "Impeachment vote"), ("2020-03", "Remote sessions begin")]


def _mpl(theme: str):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = THEMES[theme]
    plt.rcdefaults()
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "svg.hashsalt": "camara-graphs", "svg.fonttype": "path",
        "figure.facecolor": t["surface"], "axes.facecolor": t["surface"], "savefig.facecolor": t["surface"],
        "text.color": t["ink"], "axes.labelcolor": t["ink2"],
        "xtick.color": t["muted"], "ytick.color": t["muted"], "xtick.major.size": 0, "ytick.major.size": 0,
        "axes.edgecolor": t["axis"], "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": t["grid"], "grid.linewidth": 0.6,
        "axes.titlelocation": "left", "axes.titlesize": 10, "axes.titlecolor": t["ink"],
        "legend.frameon": False, "legend.labelcolor": t["ink"],
    })
    return plt, t


def _save(fig, path: Path) -> None:
    meta = {"Date": None, "Creator": None} if path.suffix == ".svg" else {"Software": None}
    fig.savefig(path, metadata=meta, bbox_inches="tight", pad_inches=0.15, dpi=200)
    import matplotlib.pyplot as plt

    plt.close(fig)


def _month_ts(months: pd.Series) -> pd.Series:
    return pd.to_datetime(months + "-01")


# ------------------------------------------------------------------ timeline

def timeline(idx: pd.DataFrame, path: Path, theme: str) -> None:
    plt, t = _mpl(theme)
    x = _month_ts(idx.month)
    covote = idx.covote_density.where(idx.votacoes_contested >= THIN)
    cosign = idx.cosponsor_density.where(idx.items_cosigned >= THIN)

    fig, axes = plt.subplots(2, 1, figsize=(10, 5.4), sharex=True, gridspec_kw={"hspace": 0.35})
    panels = [
        (axes[0], covote, "Co-voting graph density (agreement ≥ 80% on contested roll calls)"),
        (axes[1], cosign, "Co-authorship graph density (co-signed ≥ 1 item)"),
    ]
    starts = [m for m in idx.month if m.endswith("-02") and g.legislatura(m) != g.legislatura(f"{int(m[:4])}-01")]
    for ax, y, title in panels:
        ax.plot(x, y, color=t["line"], lw=2, solid_capstyle="round", solid_joinstyle="round", zorder=3)
        # A month between two gaps has no line segment; show it as a dot.
        alone = y.notna() & y.shift(1).isna() & y.shift(-1).isna()
        ax.scatter(x[alone], y[alone], s=14, color=t["line"], zorder=3, linewidths=0)
        ax.set_title(title, pad=8)
        ax.set_ylim(0, max(0.05, float(np.nanmax(y.to_numpy())) * 1.15) if y.notna().any() else 1)
        ax.margins(x=0.01)
        for m in starts:
            ax.axvline(pd.Timestamp(m + "-01"), color=t["axis"], lw=0.8, zorder=1)
    top = axes[0]
    ymax = top.get_ylim()[1]
    for m in starts:
        top.text(pd.Timestamp(m + "-01"), ymax, f" {g.legislatura(m)}th legislature",
                 va="top", ha="left", fontsize=8, color=t["ink2"])
    # Event labels sit in the empty band at the bottom of the panel, tied to
    # the line by a hairline, so they never cross the series.
    for m, label in EVENTS:
        row = idx.index[idx.month == m]
        if not len(row) or pd.isna(covote.loc[row[0]]):
            continue
        xv, yv = pd.Timestamp(m + "-01"), covote.loc[row[0]]
        top.scatter([xv], [yv], s=48, facecolors=t["surface"], edgecolors=t["line"], linewidths=2, zorder=4)
        top.annotate(label, (xv, yv), xytext=(xv, ymax * 0.04), textcoords="data", ha="center", va="bottom",
                     fontsize=8, color=t["ink2"], zorder=4,
                     bbox=dict(boxstyle="square,pad=0.15", fc=t["surface"], ec="none"),
                     arrowprops=dict(arrowstyle="-", color=t["axis"], lw=0.8, shrinkA=0, shrinkB=4))
    fig.text(0.0, -0.02,
             f"Monthly, {idx.month.iloc[0]} to {idx.month.iloc[-1]}. Gaps are months with fewer than {THIN} contested "
             f"roll calls or co-signed items (recess, campaign season). Source: Câmara dos Deputados open data.",
             fontsize=8, color=t["muted"], ha="left")
    _save(fig, path)


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


# ------------------------------------------------------------------ parties

def parties(month: str, path: Path, theme: str, data_dir=None, min_size: int = 8, **kw) -> None:
    plt, t = _mpl(theme)
    from matplotlib.colors import LinearSegmentedColormap

    G = g.graph(month, "covote", data_dir=data_dir, **kw)
    nodes = list(G.nodes)
    party = {n: G.nodes[n].get("party", "") for n in nodes}
    sizes = Counter(party.values())
    keep = [p for p, c in sizes.items() if c >= min_size and p]
    if not keep:
        return
    P = _orient(_positions(month, nodes, data_dir, **kw), [party[n] for n in nodes])
    x = pd.Series(P[:, 0], index=nodes)
    order = sorted(keep, key=lambda p: (x[[n for n in nodes if party[n] == p]].mean(), p))

    e = g.covote_edges(month, data_dir=data_dir, **{k: v for k, v in kw.items() if k in ("min_shared", "lop", "obstruction_as_no")})
    e = e[e.u.isin(nodes) & e.v.isin(nodes)]
    pu, pv = e.u.map(party), e.v.map(party)
    a = pd.DataFrame({"a": np.where(pu <= pv, pu, pv), "b": np.where(pu <= pv, pv, pu), "x": e.agreement})
    mean = a.groupby(["a", "b"]).x.mean()
    k = len(order)
    A = np.full((k, k), np.nan)
    for i, p in enumerate(order):
        for j, q in enumerate(order):
            key = (min(p, q), max(p, q))
            if key in mean.index:
                A[i, j] = mean[key]

    ramp = RAMP if theme == "light" else RAMP[::-1]
    cmap = LinearSegmentedColormap.from_list("ramp", ramp)
    side = 0.42 * k + 1.6
    fig, ax = plt.subplots(figsize=(side + 0.8, side))
    mesh = ax.pcolormesh(A, cmap=cmap, vmin=0, vmax=1, edgecolors=t["surface"], linewidth=1.5)
    for i in range(k):
        for j in range(k):
            if not np.isnan(A[i, j]):
                dark_cell = A[i, j] >= 0.55
                light_text = dark_cell if theme == "light" else not dark_cell
                ax.text(j + 0.5, i + 0.5, f"{A[i, j] * 100:.0f}", ha="center", va="center", fontsize=7.5,
                        color="#ffffff" if light_text else "#0b0b0b")
    labels = [f"{p} ({sizes[p]})" for p in order]
    ax.set_xticks(np.arange(k) + 0.5, labels, rotation=90)
    ax.set_yticks(np.arange(k) + 0.5, labels)
    ax.tick_params(colors=t["ink2"])
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(mesh, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=t["muted"], size=0)
    cb.set_label("Mean pairwise agreement (%)", color=t["ink2"])
    cb.set_ticks([0, 0.25, 0.5, 0.75, 1], labels=["0", "25", "50", "75", "100"])
    ax.set_title(f"{month}: % of contested roll calls on which two deputies voted alike", pad=30)
    ax.text(0, 1.015,
            f"Parties with at least {min_size} deputies, ordered by mean position on the first principal\n"
            f"component of the votes. Diagonal: pairs within the same party.",
            fontsize=8, color=t["muted"], ha="left", va="bottom", transform=ax.transAxes)
    _save(fig, path)


# -------------------------------------------------------------------- entry

def pictured_month(idx: pd.DataFrame, full_month: int = FULL_MONTH) -> str | None:
    full = idx[idx.votacoes_contested >= full_month]
    return full.month.iloc[-1] if len(full) else None


def render(data_dir: Path, out_dir: Path, *, full_month: int = FULL_MONTH, min_size: int = 8, **kw) -> str | None:
    """Write every chart for both themes; return the month pictured."""
    idx = pd.read_csv(data_dir / "index.csv", dtype={"month": str})
    out_dir.mkdir(parents=True, exist_ok=True)
    month = pictured_month(idx, full_month)
    for theme in THEMES:
        timeline(idx, out_dir / f"timeline-{theme}.svg", theme)
        if month:
            network(month, out_dir / f"network-{theme}.png", theme, data_dir=data_dir, **kw)
            parties(month, out_dir / f"parties-{theme}.svg", theme, data_dir=data_dir, min_size=min_size, **kw)
    return month
