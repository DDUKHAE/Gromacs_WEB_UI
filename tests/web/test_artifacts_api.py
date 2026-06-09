import json
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def harness_dir(tmp_path):
    (tmp_path / "runs").mkdir()
    return tmp_path


@pytest.fixture
def app(harness_dir):
    from web.server import create_app
    return create_app(harness_dir=harness_dir)


def _make_run(harness_dir: Path, run_id="ubq_20260609_120000", stage="viz") -> Path:
    ws = harness_dir / "runs" / run_id
    viz = ws / "stage3_viz"
    viz.mkdir(parents=True)
    (ws / "runner.pid").write_text("999999999")
    (ws / "runner.exit").write_text("0")
    (ws / "state.json").write_text(json.dumps({"last_completed_stage": stage, "current_step": 8, "pending_warnings": []}))
    return ws


def _write_xvg(path: Path, title="RMSD", xlabel="Time (ns)", ylabel="RMSD (nm)") -> None:
    path.write_text(
        f'@ title "{title}"\n'
        f'@ xaxis label "{xlabel}"\n'
        f'@ yaxis label "{ylabel}"\n'
        '0.0 0.10\n'
        '0.1 0.12\n'
        '0.2 0.11\n'
    )


async def test_artifacts_empty_before_viz(app, harness_dir):
    """stage3_viz 폴더가 없으면 빈 배열 반환."""
    ws = harness_dir / "runs" / "ubq_20260609_120000"
    ws.mkdir(parents=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/ubq_20260609_120000/artifacts")
    assert r.status_code == 200
    assert r.json() == []


async def test_artifacts_returns_parsed_xvg(app, harness_dir):
    ws = _make_run(harness_dir)
    _write_xvg(ws / "stage3_viz" / "rmsd.xvg", title="RMSD", ylabel="RMSD (nm)")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/ubq_20260609_120000/artifacts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    item = data[0]
    assert item["name"] == "rmsd"
    assert item["title"] == "RMSD"
    assert item["yaxis_label"] == "RMSD (nm)"
    assert "columns" in item
    assert len(item["columns"]) == 2  # x and y columns
    assert len(item["columns"][0]) == 3  # 3 data points


async def test_artifacts_invalid_run_id(app, harness_dir):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/runs/invalid_format_no_date/artifacts")
    assert r.status_code == 400
