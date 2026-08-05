import pytest

from lib import llm_assist


def test_client_available_false_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_assist.client_available() is False


def test_client_available_true_with_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert llm_assist.client_available() is True


def test_review_pdb_falls_back_when_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    verdict = llm_assist.review_pdb({"missing_residues": [{"chain": "A"}]}, {})
    assert verdict.proceed is True


def test_review_gro_falls_back_when_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    verdict = llm_assist.review_gro({"tier": "warning", "metric": "net_charge"})
    assert verdict.proceed is True


def test_review_md_phase_falls_back_when_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    verdict = llm_assist.review_md_phase(
        "nvt", {"tier": "warning", "metric": "temperature"}, {}, {})
    assert verdict.proceed is True
    assert verdict.accept_mutation is False


def test_review_pdb_falls_back_on_api_exception(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _BoomClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                raise RuntimeError("simulated API failure")

    monkeypatch.setattr(llm_assist, "_client", lambda: _BoomClient())
    verdict = llm_assist.review_pdb({"altloc_residues": ["A:12"]}, {})
    assert verdict.proceed is True


def test_review_md_phase_uses_parsed_output(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _FakeResponse:
        parsed_output = llm_assist.PhaseVerdict(
            proceed=True, accept_mutation=True, diagnosis="looks fine, accept the fix")

    class _FakeClient:
        class messages:
            @staticmethod
            def parse(**kwargs):
                assert kwargs["output_format"] is llm_assist.PhaseVerdict
                return _FakeResponse()

    monkeypatch.setattr(llm_assist, "_client", lambda: _FakeClient())
    verdict = llm_assist.review_md_phase(
        "nvt", {"tier": "warning", "metric": "temperature"}, {}, {})
    assert verdict.proceed is True
    assert verdict.accept_mutation is True
