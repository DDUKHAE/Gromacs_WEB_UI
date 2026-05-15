from pathlib import Path
from unittest.mock import patch


def test_animate_skipped_when_renderer_missing(tmp_path: Path):
    from skills.illustrator.illustrator import animate_trajectory
    with patch("shutil.which", return_value=None):
        out = animate_trajectory(tmp_path, output_path=tmp_path / "a.mp4")
    assert out is None


def test_animate_skipped_when_ffmpeg_missing(tmp_path: Path):
    from skills.illustrator.illustrator import animate_trajectory
    def which(x):
        return "/usr/bin/pymol" if x == "pymol" else None
    with patch("shutil.which", side_effect=which):
        out = animate_trajectory(tmp_path, output_path=tmp_path / "a.mp4")
    assert out is None
