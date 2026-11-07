"""Brazil's municipalities and states as SVG paths for the explorer pages.

IBGE's official meshes (``servicodados.ibge.gov.br/api/v3/malhas``) come as
TopoJSON. This decodes the arcs, projects them (equirectangular, with
longitude scaled by the cosine of Brazil's middle latitude, which is enough
at this size), and writes ``docs/lib/maps/{municipios,ufs}.json``: a view box
and one relative SVG path per IBGE code. The browser only draws paths.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ..fetch import get_json, log
from ..paths import REPO

MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/json&intrarregiao={level}&qualidade=minima"
WIDTH = 1000.0
LAT0 = -15.0   # Brazil's middle latitude, for the longitude scale


def _arcs(topo: dict) -> list[list[tuple[float, float]]]:
    t = topo.get("transform")
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            if t:
                x, y = x + dx, y + dy
                pts.append((x * t["scale"][0] + t["translate"][0], y * t["scale"][1] + t["translate"][1]))
            else:
                pts.append((dx, dy))
        out.append(pts)
    return out


def _ring(arcs, idx: list[int]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in idx:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def _polygons(geom: dict) -> list[list[list[int]]]:
    if geom["type"] == "Polygon":
        return [geom["arcs"]]
    if geom["type"] == "MultiPolygon":
        return geom["arcs"]
    return []


def build(level: str, topo: dict) -> dict:
    arcs = _arcs(topo)
    obj = next(iter(topo["objects"].values()))
    k = math.cos(math.radians(LAT0))
    shapes = {}
    allpts = []
    rings_by = {}
    for g in obj["geometries"]:
        code = str(g["properties"]["codarea"])
        rings = [_ring(arcs, r) for poly in _polygons(g) for r in poly]
        rings_by[code] = rings
        for r in rings:
            allpts.extend(r)
    xs = [p[0] * k for p in allpts]
    ys = [-p[1] for p in allpts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    s = WIDTH / (x1 - x0)
    height = round((y1 - y0) * s, 1)

    def proj(p):
        return round((p[0] * k - x0) * s, 1), round((-p[1] - y0) * s, 1)

    for code, rings in rings_by.items():
        parts = []
        for r in rings:
            pts = []
            for p in map(proj, r):
                if not pts or p != pts[-1]:
                    pts.append(p)
            if len(pts) < 3:
                continue
            d = [f"M{pts[0][0]:g} {pts[0][1]:g}"]
            prev = pts[0]
            rel = []
            for p in pts[1:]:
                rel.append(f"{round(p[0] - prev[0], 1):g} {round(p[1] - prev[1], 1):g}")
                prev = p
            parts.append(d[0] + "l" + " ".join(rel) + "z")
        shapes[code] = "".join(parts)
    return {"viewBox": [WIDTH, height], "shapes": dict(sorted(shapes.items()))}


def write(out: Path = REPO / "docs" / "lib" / "maps") -> None:
    out.mkdir(parents=True, exist_ok=True)
    for level, name in (("municipio", "municipios"), ("UF", "ufs")):
        topo = get_json(MALHA.format(level=level), attempts=6, timeout=180)
        if not topo:
            raise RuntimeError(f"IBGE mesh {level}: empty")
        m = build(level, topo)
        p = out / f"{name}.json"
        p.write_text(json.dumps(m, separators=(",", ":")))
        log(f"maps: {name}.json, {len(m['shapes'])} shapes, {p.stat().st_size:,} bytes")
