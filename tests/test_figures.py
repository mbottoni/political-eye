import pytest


def test_figures_render_both_themes_deterministically(built, tmp_path):
    pytest.importorskip("matplotlib")
    from camaragraphs import figures, summary

    summary.build_index(built)
    kw = dict(full_month=2, min_shared=1)
    month = figures.render(built, tmp_path / "a", **kw)
    figures.render(built, tmp_path / "b", **kw)
    assert month == "2025-03"
    names = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert names == ["network-dark.png", "network-light.png"]
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


