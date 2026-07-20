from lib import xvg_parser

SAMPLE = """\
# comment
@    title "RMSD"
@    xaxis  label "Time (ns)"
@ s0 legend "Backbone"
0.0   0.10
0.5   0.18
1.0   0.21
1.5   0.20
"""


def test_parse_text_columns_and_metadata():
    r = xvg_parser.parse_text(SAMPLE)
    assert r["columns"][0] == [0.0, 0.5, 1.0, 1.5]
    assert r["columns"][1] == [0.10, 0.18, 0.21, 0.20]
    assert "Backbone" in r["column_labels"][0]
    assert r["title"] == "RMSD"


def test_summary_stats(tmp_path):
    p = tmp_path / "rmsd.xvg"
    p.write_text(SAMPLE)
    s = xvg_parser.summary(p, column=1)
    assert s["count"] == 4
    assert abs(s["max"] - 0.21) < 1e-9


def test_ignores_comment_and_at_lines_and_blank():
    r = xvg_parser.parse_text("# x\n@ y\n\n1 2\n")
    assert r["columns"][0] == [1.0] and r["columns"][1] == [2.0]


def test_running_average_smooths():
    out = xvg_parser.running_average([0, 2, 0, 2, 0], window=3)
    assert len(out) >= 1 and max(out) <= 2.0


def test_malformed_row_is_skipped():
    r = xvg_parser.parse_text("1 2\nBROKEN\n3 4\n")
    assert r["columns"][0] == [1.0, 3.0]


def test_summary_all_returns_per_column_stats():
    stats = xvg_parser.summary_all(SAMPLE)
    assert len(stats) == 1
    assert stats[0]["count"] == 4
