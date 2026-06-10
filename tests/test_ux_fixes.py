import pytest
from unittest.mock import MagicMock


def make_info(last_stage, current_step, status="running"):
    """Build a minimal run info dict as returned by /api/runs/{id}."""
    return {
        "last_completed_stage": last_stage,
        "current_step": current_step,
        "status": status,
    }


def test_run_summary_includes_current_step():
    """_run_summary must include current_step so the frontend can use it."""
    from web.run_reader import RunInfo
    from pathlib import Path
    from web.server import _run_summary

    info = RunInfo(
        run_id="prot_20260610_120000",
        workspace=Path("/tmp/fake"),
        status="running",
        protein="prot",
        created_at="2026-06-10T12:00:00",
        last_completed_stage=None,
        current_step=3,
        pending_warnings=[],
    )
    summary = _run_summary(info)
    assert summary["current_step"] == 3
    assert "last_completed_stage" in summary
