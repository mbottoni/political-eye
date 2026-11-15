"""How big the repository is, and what makes it grow.

    uv run python scripts/size_report.py          # plain python3 works too: standard library only
    uv run python scripts/size_report.py <repo>   # another clone, bare ones included

For each source (``data/<source>/``; everything outside ``data/`` is "code"):

- working tree: the files tracked at HEAD, their size and the largest one;
- history: every version of every file reachable from any ref, raw and as
  this clone packs it, the files whose versions weigh most, and
  ``git count-objects -vH``;
- growth: a pack of everything reachable from HEAD (about what a clone of
  the default branch downloads) now and 7 and 30 days earlier, and the packed
  size of the file versions each month's commits added;
- backfills: how much of the PNCP and Siconfi histories is read, and what the
  PNCP tables would weigh if the unread days were like the read ones.

Informational only: the test workflow prints it and never fails on it. Sizes
are MiB (2^20 bytes), as git and du report them; tests/test_data_sizes.py
fails on any data file over 90 MB. Packed sizes are as stored in this clone
(GitHub's packs, for a fresh one); git keeps the newest version of a file
whole and older ones as deltas, so the latest month looks heavier than it is,
and ``git repack -adf`` gives the floor.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIB = 1024 * 1024
WARN_MIB = 50          # flag single files above this; the test fails at 90 MB


def git(*args: str, input: str | None = None, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, input=input, capture_output=True, text=True, check=True).stdout


def source_of(path: str) -> str:
    """data/pncp/contratos/2026-10.csv -> pncp; data/README.md -> data; anything else -> code."""
    parts = path.split("/")
    if parts[0] != "data":
        return "code"
    return parts[1] if len(parts) > 2 else "data"


def mib(n: float) -> str:
    return f"{n / MIB:,.1f}"


def working_tree(cwd: Path = ROOT) -> dict[str, dict]:
    """Tracked files at HEAD, by source: count, bytes, largest file."""
    out: dict[str, dict] = defaultdict(lambda: {"files": 0, "bytes": 0, "largest": ("", 0)})
    for entry in git("ls-tree", "-r", "-l", "-z", "HEAD", cwd=cwd).split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        _mode, kind, _sha, size = meta.split()
        if kind != "blob":
            continue
        s = out[source_of(path)]
        s["files"] += 1
        s["bytes"] += int(size)
        if int(size) > s["largest"][1]:
            s["largest"] = (path, int(size))
    return dict(out)


def blobs(cwd: Path = ROOT) -> dict[str, tuple[str, int, int]]:
    """Every blob reachable from any ref: sha -> (first path seen, raw bytes, packed bytes)."""
    paths = {}
    for line in git("rev-list", "--objects", "--all", cwd=cwd).splitlines():
        sha, _, path = line.partition(" ")
        paths[sha] = path
    info = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize) %(objectsize:disk)",
               input="\n".join(paths) + "\n", cwd=cwd)
    out = {}
    for line in info.splitlines():
        sha, kind, size, disk = line.split()
        if kind == "blob":
            out[sha] = (paths[sha], int(size), int(disk))
    return out


def growth(sizes: dict[str, tuple[str, int, int]], cwd: Path = ROOT) -> list[tuple[str, str, int]]:
    """(commit day, source, packed bytes) for each file version, at the first commit on HEAD that added it."""
    seen, out, day = set(), [], ""
    log = git("log", "--raw", "--no-renames", "--no-abbrev", "--reverse", "--format=@%cs", "HEAD", cwd=cwd)
    for line in log.splitlines():
        if line.startswith("@"):
            day = line[1:]
        elif line.startswith(":"):
            meta, path = line.split("\t", 1)
            sha = meta.split()[3]
            if set(sha) == {"0"} or sha in seen or sha not in sizes:
                continue
            seen.add(sha)
            out.append((day, source_of(path), sizes[sha][2]))
    return out


def pack_size(rev: str, cwd: Path = ROOT) -> int:
    """Bytes of one pack holding everything reachable from ``rev``."""
    objs = subprocess.Popen(["git", "rev-list", "--objects", rev], cwd=cwd, stdout=subprocess.PIPE)
    pack = subprocess.Popen(["git", "pack-objects", "--stdout", "-q"], cwd=cwd, stdin=objs.stdout,
                            stdout=subprocess.PIPE)
    objs.stdout.close()
    n = 0
    while chunk := pack.stdout.read(1 << 20):
        n += len(chunk)
    if pack.wait() or objs.wait():
        raise subprocess.CalledProcessError(1, f"git pack-objects {rev}")
    return n


def table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    fmt = lambda r: "  ".join(str(c).ljust(w) if i == 0 else str(c).rjust(w) for i, (c, w) in enumerate(zip(r, widths)))
    return "\n".join(["  " + fmt(header), *("  " + fmt(r) for r in rows)])


def backfills(cwd: Path = ROOT, pncp_bytes: int = 0) -> list[str]:
    lines = []
    try:
        c = json.loads(git("show", "HEAD:data/site/pncp/resumo.json", cwd=cwd))["coverage"]
        share = c["days_read"] / c["span_days"]
        lines.append(f"  pncp: {c['days_read']:,} of {c['span_days']:,} days read ({share:.1%}), "
                     f"{c['first']} to {c['last']}, back to {c['since']}")
        lines.append(f"        data/pncp would be about {mib(pncp_bytes / share)} MiB (now {mib(pncp_bytes)}) "
                     "if every unread day were like the read ones; an upper bound, since far fewer contracts "
                     "were published before 2024")
    except (KeyError, ValueError, ZeroDivisionError, subprocess.CalledProcessError) as e:
        lines.append(f"  pncp: coverage unavailable ({e.__class__.__name__})")
    try:
        cov = json.loads(git("show", "HEAD:data/site/siconfi/resumo.json", cwd=cwd))["coverage"]
        towns = int(git("show", "HEAD:data/siconfi/entes.csv", cwd=cwd).count("\n")) - 1
        missing = [c["ano"] for c in cov if c["consultados"] < towns]
        years = f"{cov[0]['ano']}-{cov[-1]['ano']}" if cov else "none"
        state = "every town consulted in every year" if not missing else f"years not finished: {missing}"
        lines.append(f"  siconfi: {years}, {towns:,} towns: {state}")
    except (KeyError, ValueError, IndexError, subprocess.CalledProcessError) as e:
        lines.append(f"  siconfi: coverage unavailable ({e.__class__.__name__})")
    return lines


def main(cwd: Path = ROOT) -> None:
    head = git("log", "-1", "--format=%h %cs", cwd=cwd).strip()
    print(f"Repository size at {head}  (MiB)\n")

    wt = working_tree(cwd)
    total = sum(s["bytes"] for s in wt.values())
    rows = [[k, s["files"], mib(s["bytes"]), f"{s['largest'][0]} ({mib(s['largest'][1])})"]
            for k, s in sorted(wt.items(), key=lambda kv: -kv[1]["bytes"])]
    print("Working tree: files tracked at HEAD")
    print(table(rows + [["total", sum(s["files"] for s in wt.values()), mib(total), ""]],
                ["source", "files", "MiB", "largest file (MiB)"]))
    big = [(p, n) for p, n in (s["largest"] for s in wt.values()) if n > WARN_MIB * MIB]
    print(f"  files over {WARN_MIB} MiB: " + (", ".join(f"{p} ({mib(n)})" for p, n in big) or "none"))

    print("\nHistory: every version of every file reachable from any ref")
    if git("rev-parse", "--is-shallow-repository", cwd=cwd).strip() == "true":
        print("  (shallow clone: only the fetched commits are counted; use fetch-depth: 0)")
    for line in git("count-objects", "-vH", cwd=cwd).splitlines():
        if line.split(":")[0] in ("count", "size", "in-pack", "size-pack"):
            print(f"  git count-objects: {line}")
    sizes = blobs(cwd)
    by = defaultdict(lambda: [0, 0, 0])
    for path, raw, disk in sizes.values():
        b = by[source_of(path)]
        b[0] += 1
        b[1] += raw
        b[2] += disk
    rows = [[k, n, mib(raw), mib(disk)] for k, (n, raw, disk) in sorted(by.items(), key=lambda kv: -kv[1][2])]
    print(table(rows + [["total", len(sizes), mib(sum(v[1] for v in sizes.values())), mib(sum(v[2] for v in sizes.values()))]],
                ["source", "versions", "raw MiB", "packed MiB"]))
    per_file = defaultdict(lambda: [0, 0, 0])
    for path, raw, disk in sizes.values():
        f = per_file[path]
        f[0] += 1
        f[1] = max(f[1], raw)
        f[2] += disk
    rows = [[path, n, mib(raw), mib(disk)] for path, (n, raw, disk) in sorted(per_file.items(), key=lambda kv: -kv[1][2])[:10]]
    print("  files whose versions weigh most:")
    print(table(rows, ["file", "versions", "largest MiB", "packed MiB"]).replace("\n  ", "\n    ").replace("  ", "    ", 1))

    print("\nGrowth")
    now = pack_size("HEAD", cwd)
    print(f"  pack of everything reachable from HEAD: {mib(now)} MiB")
    last = dt.date.fromisoformat(head.split()[1])
    for days in (7, 30):
        since = (last - dt.timedelta(days=days)).isoformat()
        old = git("rev-list", "-1", "--first-parent", f"--before={since}T23:59:59", "HEAD", cwd=cwd).strip()
        if not old:
            print(f"  {days} days earlier ({since}): no commit yet")
            continue
        then = pack_size(old, cwd)
        print(f"  {days} days earlier ({since}, {old[:7]}): {mib(then)} MiB, so +{mib(now - then)} MiB, "
              f"{mib((now - then) / days)} MiB a day")

    g = growth(sizes, cwd)
    if g:
        months = sorted({d[:7] for d, _, _ in g})
        top = [k for k, _ in Counter({k: v[2] for k, v in by.items()}).most_common(6)]
        per = defaultdict(int)
        for d, src, n in g:
            per[(d[:7], src if src in top else "other")] += n
        cols = top + (["other"] if any(k[1] == "other" for k in per) else [])
        rows = [[m, mib(sum(per[(m, c)] for c in cols)), *(mib(per[(m, c)]) for c in cols)] for m in months]
        print("  packed size of the file versions each month's commits added, by source:")
        print(table(rows, ["month", "total", *cols]).replace("\n  ", "\n    ").replace("  ", "    ", 1))

    print("\nBackfills")
    for line in backfills(cwd, wt.get("pncp", {}).get("bytes", 0)):
        print(line)


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT)
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"size_report: {e}")
