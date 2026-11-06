"""Per-month summary (``data/index.csv``) and the generated tables in README.md."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
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
    rows = [month_row(m, data_dir) for m in g.months(data_dir)]
    df = pd.DataFrame(rows)
    df.to_csv(data_dir / "index.csv", index=False, lineterminator="\n")
    return df


def _fmt(x, digits=3) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "--"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return f"{x:,}"


def recent_table(df: pd.DataFrame, n: int = 12) -> str:
    head = (
        "| month | roll calls (contested) | co-voting nodes | edges | density | mean agreement "
        "| co-authorship nodes | edges | density | aligned nodes |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    lines = []
    for r in df.tail(n).iloc[::-1].itertuples():
        lines.append(
            f"| {r.month} | {r.votacoes} ({r.votacoes_contested}) | {_fmt(r.covote_nodes)} | {_fmt(r.covote_edges)} "
            f"| {_fmt(r.covote_density)} | {_fmt(r.mean_agreement)} | {_fmt(r.cosponsor_nodes)} "
            f"| {_fmt(r.cosponsor_edges)} | {_fmt(r.cosponsor_density)} | {_fmt(r.aligned_nodes)} |"
        )
    return head + "\n".join(lines)


def coverage(df: pd.DataFrame) -> str:
    out = []
    for leg, x in df.groupby("legislatura"):
        out.append(
            f"| {leg} | {x.month.min()} → {x.month.max()} | {len(x)} | {int(x.votacoes.sum()):,} "
            f"| {int(x.votacoes_contested.sum()):,} | {int(x.items_cosigned.sum()):,} |"
        )
    return (
        "| legislatura | from → to | months | roll calls | contested | co-signed items |\n"
        "|---|---|---:|---:|---:|---:|\n" + "\n".join(out)
    )


def _replace(text: str, tag: str, body: str) -> str:
    pat = re.compile(rf"(<!-- BEGIN:{tag} -->\n).*?(<!-- END:{tag} -->)", re.S)
    if not pat.search(text):
        raise ValueError(f"README.md is missing the {tag} markers")
    return pat.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)


def replace_block(readme: Path, tag: str, body: str) -> None:
    readme.write_text(_replace(readme.read_text(), tag, body))


def update_readme(readme: Path, df: pd.DataFrame) -> None:
    text = readme.read_text()
    for tag, body in (("RECENT", recent_table(df)), ("COVERAGE", coverage(df))):
        text = _replace(text, tag, body)
    readme.write_text(text)


EXPLORER = "https://mbottoni.github.io/camara-graphs/"


def party_block(month: str, views: list[dict]) -> str:
    """Click-to-expand party views: the only interaction a README allows."""
    from html import escape
    from urllib.parse import quote

    out = [f"Click a party to see its deputies (dark) against everyone else in {month}, with everyone they "
           f"vote together and sign together with. Each image opens that party in the explorer.\n"]
    for v in views:
        p = escape(v["party"])
        near = f"closest: {escape(v['nearest'][0])} ({v['nearest'][1]:.0%})" if v["nearest"] else ""
        far = f"farthest: {escape(v['farthest'][0])} ({v['farthest'][1]:.0%})" if v["farthest"] else ""
        bits = " · ".join(x for x in (f"{v['size']} deputies", f"agree with each other {v['cohesion']:.0%}", near, far) if x)
        link = f"{EXPLORER}?month={month}&amp;a={quote(v['party'])}"
        out.append(
            f"<details>\n<summary><b>{p}</b> · {bits}</summary>\n\n"
            f"<a href=\"{link}\"><picture>\n"
            f"  <source media=\"(prefers-color-scheme: dark)\" srcset=\"figures/{v['files']['dark']}\">\n"
            f"  <img alt=\"{p} deputies and their vote-together and sign-together edges in {month}\" "
            f"src=\"figures/{v['files']['light']}\">\n"
            f"</picture></a>\n\n"
            f"{p} deputies vote alike (≥ 80% of shared votes) with {v['vote_partners']} deputies outside the party, "
            f"and co-signed with {v['sign_partners']} deputies, {v['sign_outside']:.0%} of them from other parties.\n\n"
            f"</details>"
        )
    return "\n".join(out)
