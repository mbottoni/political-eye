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



def test_party_views_and_readme_block(built, tmp_path):
    pytest.importorskip("matplotlib")
    from camaragraphs import figures, summary

    out = tmp_path / "fig"
    out.mkdir()
    (out / "party-GONE-light.png").write_bytes(b"stale")
    views = figures.render_parties("2025-03", out, built, min_size=1, min_shared=1)
    names = sorted(p.name for p in out.glob("party-*.png"))
    assert "party-GONE-light.png" not in names                      # stale view removed
    assert {v["party"] for v in views} == {"P1", "B"}
    assert all((out / f).exists() for v in views for f in v["files"].values())
    b = next(v for v in views if v["party"] == "B")                 # deputy 20 alone
    # co-signs items 1, 2 and the 5-signer PEC (under the default 50 cap): 10, 30, 40, 100
    assert b["size"] == 1 and b["sign_partners"] == 4 and b["sign_outside"] == 1.0
    block = summary.party_block("2025-03", views)
    assert block.count("<details>") == 2 and "a=B" in block
