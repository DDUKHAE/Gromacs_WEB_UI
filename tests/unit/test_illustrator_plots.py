from pathlib import Path


def _write_xvg(p: Path, n: int = 100):
    lines = ['@ title "t"\n', '@ xaxis label "x"\n', '@ yaxis label "y"\n']
    for i in range(n):
        lines.append(f"{i} {i*0.1:.3f}\n")
    p.write_text("".join(lines))


def test_plot_xvg_creates_png(tmp_path: Path):
    from skills.illustrator.illustrator import plot_xvg
    xvg = tmp_path / "rmsd.xvg"
    _write_xvg(xvg)
    png = plot_xvg(xvg, output_path=tmp_path / "rmsd.png", title="RMSD")
    assert png.exists()
    assert png.stat().st_size > 0


def test_plot_all_creates_one_png_per_xvg(tmp_path: Path):
    from skills.illustrator.illustrator import plot_all
    (tmp_path / "stage3_viz").mkdir(parents=True)
    for name in ("rmsd.xvg", "rmsf.xvg", "gyrate.xvg"):
        _write_xvg(tmp_path / "stage3_viz" / name)
    pngs = plot_all(tmp_path)
    assert len(pngs) == 3
    for p in pngs:
        assert p.suffix == ".png"
        assert p.exists()
