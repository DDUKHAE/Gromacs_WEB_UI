import pytest
from lib.protonation import is_propka_available, run_propka, _parse_propka_output


def test_is_propka_available_returns_bool():
    assert isinstance(is_propka_available(), bool)


def test_parse_empty_output():
    result = _parse_propka_output("", 7.0)
    assert result["available"] is True
    assert result["his_states"] == {}
    assert result["pka_list"] == []


def test_parse_his_below_ph_gives_hsd():
    # HIS pKa 6.0 < pH 7.0 → deprotonated = HSD
    mock = "\nSUMMARY OF THIS PREDICTION\n---\nHIS   15    A      6.00\n---\n"
    result = _parse_propka_output(mock, 7.0)
    assert result["his_states"]["A:15"] == "HSD"


def test_parse_his_above_ph_gives_hsp():
    # HIS pKa 8.0 > pH 7.0 → protonated = HSP
    mock = "\nSUMMARY OF THIS PREDICTION\n---\nHIS   57    A      8.00\n---\n"
    result = _parse_propka_output(mock, 7.0)
    assert result["his_states"]["A:57"] == "HSP"


def test_parse_multiple_residues():
    mock = (
        "\nSUMMARY OF THIS PREDICTION\n---\n"
        "HIS   15    A      6.00\n"
        "HIS   57    A      8.00\n"
        "ASP   26    A      3.80\n"
        "---\n"
    )
    result = _parse_propka_output(mock, 7.0)
    assert result["his_states"]["A:15"] == "HSD"
    assert result["his_states"]["A:57"] == "HSP"
    assert len(result["pka_list"]) == 3


def test_run_propka_returns_dict_when_unavailable(monkeypatch):
    monkeypatch.setattr("lib.protonation.is_propka_available", lambda: False)
    from pathlib import Path
    result = run_propka(Path("/nonexistent.pdb"), ph=7.0)
    assert result["available"] is False
    assert result["his_states"] == {}
