from pathlib import Path

from web import runner


def test_viz_runner_uses_full_illustrator_entry_point(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("skills.illustrator.illustrator.illustrate",
                        lambda **kwargs: calls.append(kwargs) or {"report_path": "report.md"})

    result = runner._run_viz(Path(tmp_path))

    assert result == {"report_path": "report.md"}
    assert calls == [{"workspace_dir": Path(tmp_path), "interactive": False}]
