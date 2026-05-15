# tests/unit/test_xvg_parser.py
from pathlib import Path
from lib import xvg_parser as X


def _write_xvg(p: Path, n: int = 1000):
    lines = ["@ title \"test\"\n", "@ xaxis label \"Time (ps)\"\n",
             "@ yaxis label \"Energy (kJ/mol)\"\n"]
    for i in range(n):
        lines.append(f"{i*10:.3f} {-12345.0 + i*0.1:.3f}\n")
    p.write_text("".join(lines))


def test_parse_basic_xvg(tmp_path: Path):
    p = tmp_path / "energy.xvg"
    _write_xvg(p, n=200)
    data = X.parse(p)
    assert data["title"] == "test"
    assert data["xaxis_label"] == "Time (ps)"
    assert data["yaxis_label"] == "Energy (kJ/mol)"
    assert len(data["columns"]) == 2  # x and y


def test_parse_downsamples_to_target(tmp_path: Path):
    p = tmp_path / "energy.xvg"
    _write_xvg(p, n=5000)
    data = X.parse(p, max_points=500)
    assert len(data["columns"][0]) <= 500
    assert len(data["columns"][1]) <= 500


def test_summary_stats(tmp_path: Path):
    p = tmp_path / "energy.xvg"
    _write_xvg(p, n=100)
    s = X.summary(p)
    assert s["count"] == 100
    assert s["min"] < s["max"]
    assert "mean" in s and "std" in s


def test_skip_comments_and_legend(tmp_path: Path):
    p = tmp_path / "x.xvg"
    p.write_text("# comment\n@ title \"t\"\n@s0 legend \"a\"\n1 2\n3 4\n")
    data = X.parse(p)
    assert data["columns"][0] == [1.0, 3.0]
    assert data["columns"][1] == [2.0, 4.0]
