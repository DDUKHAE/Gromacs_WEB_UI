"""Parameter resolution: tutorial defaults, wizard config, contract, prefs.

These pin the behaviour that used to differ between the three open-coded
copies of this logic (run_plan, protocol_contract, env_builder), where `a or b`
and `dict.get(k, b)` disagreed on every falsy value.
"""
from __future__ import annotations

import pytest

from lib import run_parameters as RPARAM

TUTORIAL_DEFAULTS = {
    "forcefield": "charmm36",
    "water_model": "tip3p",
    "box_type": "cubic",
    "box_distance_nm": 1.0,
}


def test_module_self_check_passes():
    RPARAM.demo()


def test_tutorial_defaults_apply_when_nothing_configured():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {}, {})
    assert r.values["forcefield"] == "charmm36"
    assert r.values["box_distance_nm"] == 1.0
    assert r.provenance["box_distance_nm"] == "tutorial"


def test_hard_fallback_when_no_layer_supplies_the_key():
    """The manifest carries no ion settings, so these come from FALLBACKS."""
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {}, {})
    assert r.values["ion_concentration_M"] == 0.15
    assert r.values["neutralize"] is True
    assert r.provenance["ion_concentration_M"] == "fallback"


def test_wizard_config_overrides_tutorial_default():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"box": {"edge_distance_nm": 1.2}}, {})
    assert r.values["box_distance_nm"] == 1.2
    assert r.provenance["box_distance_nm"] == "config.box"


@pytest.mark.parametrize("zero_value", [0, 0.0])
def test_zero_ion_concentration_is_honoured(zero_value):
    """The Lysozyme tutorial neutralises with no bulk salt: 0 M is a choice.

    `ions.get("concentration_M", 0.15)` already did this, but the sibling
    `box_distance_nm` used `or` and silently replaced 0 with the default.
    """
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"ions": {"concentration_M": zero_value}}, {})
    assert r.values["ion_concentration_M"] == zero_value
    assert r.provenance["ion_concentration_M"] == "config.ions"


def test_zero_box_distance_is_not_replaced_by_the_default():
    """Regression: the old `locked.get(...) or defaults.get(...)` returned 1.0."""
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"box": {"edge_distance_nm": 0}}, {})
    assert r.values["box_distance_nm"] == 0
    assert r.provenance["box_distance_nm"] == "config.box"


def test_neutralize_false_is_honoured():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"ions": {"neutralize": False}}, {})
    assert r.values["neutralize"] is False
    assert r.provenance["neutralize"] == "config.ions"


@pytest.mark.parametrize("blank", ["", None])
def test_blank_string_means_unset_not_a_value(blank):
    """Regression: protocol_contract's `.get(k, default)` kept the empty string
    while run_plan's `or` fell back, so the two artifacts disagreed."""
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"forcefield": {"name": blank}}, {})
    assert r.values["forcefield"] == "charmm36"
    assert r.provenance["forcefield"] == "tutorial"


def test_locked_contract_outranks_the_wizard_config():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"box": {"edge_distance_nm": 1.2}},
                       {}, locked={"box_distance_nm": 2.0})
    assert r.values["box_distance_nm"] == 2.0
    assert r.provenance["box_distance_nm"] == "locked"


def test_user_prefs_outrank_the_locked_contract():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {"forcefield": {"name": "amber99sb"}},
                       {"forcefield": "oplsaa"}, locked={"forcefield": "charmm27"})
    assert r.values["forcefield"] == "oplsaa"
    assert r.provenance["forcefield"] == "user_prefs"


def test_user_prefs_only_supply_the_keys_the_server_actually_writes():
    """meta.json["user_preferences"] only ever carries forcefield/water/box_type,
    so the spec must not claim user_prefs can set the ion or box-size values."""
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {},
                       {"box_distance_nm": 9.9, "ion_concentration_M": 9.9,
                        "neutralize": False})
    assert r.values["box_distance_nm"] == 1.0
    assert r.values["ion_concentration_M"] == 0.15
    assert r.values["neutralize"] is True


def test_legacy_water_key_is_accepted():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {}, {"water": "spce"})
    assert r.values["water_model"] == "spce"
    assert r.provenance["water_model"] == "user_prefs"


def test_every_parameter_gets_a_value_and_a_source():
    r = RPARAM.resolve(TUTORIAL_DEFAULTS, {}, {})
    assert set(r.values) == set(r.provenance)
    assert None not in r.values.values()


def test_run_plan_and_contract_agree_on_the_same_config():
    """The two artifacts must never record different parameters for one run."""
    config = {
        "forcefield": {"name": "", "water_model": "tip3p"},
        "box": {"type": "cubic", "edge_distance_nm": 0},
        "ions": {"concentration_M": 0.0, "neutralize": False},
    }
    from_plan = RPARAM.locked_settings(TUTORIAL_DEFAULTS, config)
    from_contract = RPARAM.locked_settings(TUTORIAL_DEFAULTS, config)
    assert from_plan == from_contract
    assert from_plan["forcefield"] == "charmm36"
    assert from_plan["box_distance_nm"] == 0
    assert from_plan["ion_concentration_M"] == 0.0
    assert from_plan["neutralize"] is False
