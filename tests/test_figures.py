import pytest


def test_figures_render_both_themes_deterministically(built, tmp_path):
    pytest.importorskip("matplotlib")
    from camaragraphs import figures, summary

    summary.build_index(built)
    kw = dict(full_month=2, min_size=1, min_shared=1)
    month = figures.render(built, tmp_path / "a", **kw)
    figures.render(built, tmp_path / "b", **kw)
    assert month == "2025-03"
    names = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert names == [f"{k}-{t}.{ext}" for k, ext in (("network", "png"), ("parties", "svg"), ("timeline", "svg"))
                     for t in ("dark", "light")]
    for n in names:
        assert (tmp_path / "a" / n).read_bytes() == (tmp_path / "b" / n).read_bytes(), n


def test_pca_signs_are_pinned():
    import numpy as np
    from camaragraphs.figures import _pca2

    rng = np.random.default_rng(0)
    M = rng.choice(np.array([-1, 0, 1], dtype=np.int8), size=(40, 25))
    perm = rng.permutation(40)
    P = _pca2(M)
    Q = np.empty_like(P)
    Q[perm] = _pca2(M[perm])   # same deputies in another order
    assert np.allclose(P, Q)
    # Negating every vote flips the raw SVD signs, just as a different BLAS
    # might; pinning must give back the same picture.
    assert np.allclose(_pca2(-M), _pca2(M))


def test_readme_map_points_and_markers(built, tmp_path):
    pytest.importorskip("matplotlib")
    import json
    from camaragraphs import readme_map

    fc = readme_map.feature_collection("2025-03", built, min_shared=1)
    assert [f["geometry"]["type"] for f in fc["features"]] == ["Point"] * 4   # deputies 10, 20, 30, 40
    props = {f["properties"]["Deputy"]: f["properties"] for f in fc["features"]}
    assert props["Ana"]["Party"] == "P1 · SP"
    assert props["Ana"]["Closest ally"].startswith("Bia (B, 100%")
    readme = tmp_path / "README.md"
    readme.write_text("a\n<!-- BEGIN:MAP -->\n<!-- END:MAP -->\nb\n")
    readme_map.update_readme(readme, "2025-03", built, min_shared=1)
    once = readme.read_text()
    readme_map.update_readme(readme, "2025-03", built, min_shared=1)
    assert readme.read_text() == once and once.endswith("b\n")
    body = once.split("```geojson\n")[1].split("\n```")[0]
    assert len(json.loads(body)["features"]) == 4   # the fenced block is valid GeoJSON
