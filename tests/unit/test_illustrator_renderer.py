from pathlib import Path
from unittest.mock import patch


def test_renderer_picks_pymol_when_available():
    from skills.illustrator.illustrator import select_renderer
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/pymol"
               if x == "pymol" else None):
        assert select_renderer() == "pymol"


def test_renderer_falls_back_to_vmd():
    from skills.illustrator.illustrator import select_renderer
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/vmd"
               if x == "vmd" else None):
        assert select_renderer() == "vmd"


def test_renderer_falls_back_to_matplotlib_only():
    from skills.illustrator.illustrator import select_renderer
    with patch("shutil.which", return_value=None):
        assert select_renderer() == "none"


def test_render_frame_returns_none_when_no_renderer(tmp_path: Path):
    from skills.illustrator.illustrator import render_frame
    with patch("shutil.which", return_value=None):
        result = render_frame(
            workspace_dir=tmp_path, frame="last",
            output_path=tmp_path / "frame_last.png")
    assert result is None
