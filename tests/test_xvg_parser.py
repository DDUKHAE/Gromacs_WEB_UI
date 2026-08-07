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


# --- plot_kind / label_for: shared by the PNG and the web UI -----------------
# Both illustrator.plot_xvg and /api/runs/{id}/artifacts read these, so a card
# in the Results tab cannot disagree with the plot it opens.

_TIME_SERIES = {"columns": [[0, 1, 2], [1.0, 1.1, 1.2]]}


def test_plot_kind_series_for_a_plain_time_series():
    assert xvg_parser.plot_kind("rmsd", _TIME_SERIES) == "series"


def test_plot_kind_series_covers_every_extra_column():
    """gyrate ships Rg plus Rg_x/Rg_y/Rg_z; all four belong on the plot."""
    gyrate = {"columns": [[0, 1], [1.4, 1.4], [1.2, 1.2], [1.0, 1.0], [1.2, 1.2]]}
    assert xvg_parser.plot_kind("gyrate", gyrate) == "series"


def test_plot_kind_scatter_for_a_2d_projection():
    """A PCA file's x axis is PC1, not time, so it must not be drawn vs index."""
    assert xvg_parser.plot_kind("pca_proj", _TIME_SERIES) == "scatter"
    assert xvg_parser.plot_kind("eigenvec_proj", _TIME_SERIES) == "scatter"


def test_plot_kind_single_for_one_column():
    assert xvg_parser.plot_kind("whatever", {"columns": [[1.0, 2.0]]}) == "single"
    assert xvg_parser.plot_kind("whatever", {"columns": []}) == "single"


def test_plot_kind_needs_two_columns_to_scatter():
    assert xvg_parser.plot_kind("pca_proj", {"columns": [[1.0, 2.0]]}) == "single"


def test_label_for_distinguishes_gmx_energy_outputs():
    """gmx energy stamps "GROMACS Energies" into every file it writes."""
    def energy(legend, unit):
        return {"title": "GROMACS Energies", "column_labels": [legend],
                "yaxis_label": unit, "columns": [[0], [0]]}

    labels = {
        xvg_parser.label_for(energy("Density", "(kg/m^3)"), "energy_density"),
        xvg_parser.label_for(energy("Temperature", "(K)"), "energy_temperature"),
        xvg_parser.label_for(energy("Pressure", "(bar)"), "energy_pressure"),
    }
    assert labels == {"Density (kg/m³)", "Temperature (K)", "Pressure (bar)"}


def test_label_for_decodes_xmgrace_superscripts():
    parsed = {"title": "Solvent Accessible Surface", "column_labels": ["Total"],
              "yaxis_label": r"(nm\S2\N)", "columns": [[0], [0]]}
    assert xvg_parser.label_for(parsed, "sasa") == "Solvent Accessible Surface (nm²)"


def test_label_for_drops_a_trailing_parenthetical():
    parsed = {"title": "Radius of gyration (total and around axes)",
              "column_labels": ["Rg"], "yaxis_label": "Radius (nm)",
              "columns": [[0], [0]]}
    assert xvg_parser.label_for(parsed, "gyrate") == "Radius of gyration"


def test_label_for_falls_back_to_the_file_name():
    assert xvg_parser.label_for({"columns": [[0], [0]]}, "my_metric") == "my metric"
