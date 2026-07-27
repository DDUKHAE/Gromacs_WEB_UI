import asyncio
from io import BytesIO

import pytest

pytest.importorskip("fastapi")
from fastapi import UploadFile

from web.server import _materialize_workflow_uploads


def test_workflow_uploads_only_materialize_declared_relative_paths(tmp_path):
    config = {"advanced_workflow": {"umbrella": {
        "index": "inputs/umbrella/index.ndx",
        "windows": [{"id": "000", "coordinate": "inputs/umbrella/window_000.gro"}],
    }}}
    uploads = [
        UploadFile(BytesIO(b"[ System ]\n"), filename="index.ndx"),
        UploadFile(BytesIO(b"coordinates\n"), filename="window_000.gro"),
    ]

    asyncio.run(_materialize_workflow_uploads(tmp_path, config, uploads))

    assert (tmp_path / "inputs/umbrella/index.ndx").read_bytes() == b"[ System ]\n"
    assert (tmp_path / "inputs/umbrella/window_000.gro").read_bytes() == b"coordinates\n"
