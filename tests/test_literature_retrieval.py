import json
import sys
import types

import pytest

from lib import literature_retrieval as lr
from lib import protocol_contract as pc
from lib import state


def _prepared_workspace(tmp_path):
    pc.materialize(tmp_path, "Lysozyme_in_water")
    (tmp_path / "literature").mkdir()
    (tmp_path / "literature" / "source.txt").write_text("A permitted paper.")
    state.write(tmp_path, state.initial(tmp_path))


def test_paperqa_result_is_evidence_only_and_preserves_contract(tmp_path, monkeypatch):
    _prepared_workspace(tmp_path)
    fake = types.ModuleType("paperqa")

    class Settings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def ask(question, settings):
        assert settings.kwargs["temperature"] == 0.0
        return "Supported by (Example2026 pages 4-5)."

    fake.Settings = Settings
    fake.ask = ask
    monkeypatch.setattr(lr.importlib.util, "find_spec", lambda _: object())
    monkeypatch.setitem(sys.modules, "paperqa", fake)

    before = json.loads((tmp_path / pc.FILENAME).read_text())
    result = lr.query_local_corpus(
        tmp_path, "How should a Zn site be parameterized?",
        {"target": "topology", "value": "investigate Zn parameters"},
    )

    assert result["execution_policy"] == "requires_user_approval"
    assert result["contract_modified"] is False
    assert result["citation_markers"] == ["Example2026 pages 4-5"]
    assert json.loads((tmp_path / pc.FILENAME).read_text()) == before
    assert (tmp_path / result["record_path"]).is_file()
    assert state.read(tmp_path)["literature_escalations"][0]["record_path"] == result["record_path"]


def test_literature_query_requires_local_corpus_and_optional_package(tmp_path):
    pc.materialize(tmp_path, "Lysozyme_in_water")
    with pytest.raises(lr.LiteratureRetrievalError, match="no local literature corpus"):
        lr.query_local_corpus(tmp_path, "Any evidence?")
