from fastapi.testclient import TestClient
from web.server import create_app
from pathlib import Path


def test_ngl_js_is_served():
    """NGL.js must be served from /static/ngl.js (not CDN)."""
    client = TestClient(create_app(Path(__file__).parent.parent))
    resp = client.get("/static/ngl.js")
    assert resp.status_code == 200
    assert len(resp.content) > 100_000, "ngl.js is suspiciously small — may not have downloaded"
    # NGL exports a Stage class; its name appears in the bundle
    assert b"Stage" in resp.content
