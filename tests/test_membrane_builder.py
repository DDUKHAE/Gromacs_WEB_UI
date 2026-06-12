import pytest
from pathlib import Path
from lib.membrane_builder import (
    is_packmol_memgen_available,
    list_supported_lipids,
    SUPPORTED_LIPIDS,
)


def test_is_packmol_memgen_available_returns_bool():
    assert isinstance(is_packmol_memgen_available(), bool)


def test_list_supported_lipids_returns_8_species():
    assert len(list_supported_lipids()) == 8


def test_list_supported_lipids_all_have_required_keys():
    for lipid in list_supported_lipids():
        for key in ("name", "full_name", "charge", "description"):
            assert key in lipid, f"Missing key '{key}' in lipid {lipid}"


def test_list_supported_lipids_contains_expected_names():
    names = {l["name"] for l in list_supported_lipids()}
    assert names == {"POPC", "POPE", "POPS", "DPPC", "DPPE", "DPPS", "CHL1", "PSM"}


def test_supported_lipids_charge_types():
    charges = {l["name"]: l["charge"] for l in list_supported_lipids()}
    assert charges["POPS"] == -1
    assert charges["DPPS"] == -1
    assert charges["POPC"] == 0
    assert charges["CHL1"] == 0
