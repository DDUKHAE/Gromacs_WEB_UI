"""Single place where a run's build parameters are decided.

Three layers can supply a value, in increasing priority:

1. the tutorial manifest's ``defaults`` — what the published tutorial used
2. ``system_config.json`` — the System Builder wizard's submission, which is a
   tutorial preset plus whatever the user changed on top of it
3. ``locked`` — the protocol contract's locked parameters, i.e. the values this
   run committed to. Only the builder consults this; the plan and the contract
   are what produce it.
4. ``user_prefs`` — legacy per-run overrides, kept for workspaces created
   before protocol contracts existed

This used to be open-coded in three places (``run_plan.compile_plan``,
``protocol_contract.materialize`` and ``env_builder.build_environment``) with
three different rules: some keys used ``a or b``, others ``dict.get(k, b)``,
and only some consulted ``user_prefs``. The two spellings disagree whenever a
value is falsy, so a concentration of ``0`` was honoured while a box distance
of ``0`` silently became the tutorial default, and the plan and the contract
could record different force fields for the same run.

The rule here is uniform: a layer supplies a value when the key is present and
the value is neither ``None`` nor an empty string. ``0`` and ``False`` are real
values — "no added salt" is a choice a tutorial makes, not a missing setting.
"""
from __future__ import annotations

from typing import Any, NamedTuple


class _Source(NamedTuple):
    """Where one parameter can come from within a layer."""
    layer: str
    keys: tuple[str, ...]


# Ordered lowest priority first; later sources win.
_SPEC: dict[str, tuple[_Source, ...]] = {
    "forcefield": (
        _Source("tutorial", ("forcefield",)),
        _Source("config.forcefield", ("name",)),
        _Source("locked", ("forcefield",)),
        _Source("user_prefs", ("forcefield",)),
    ),
    "water_model": (
        _Source("tutorial", ("water_model",)),
        _Source("config.forcefield", ("water_model",)),
        _Source("locked", ("water_model",)),
        # The legacy key "water" predates "water_model"; accept both.
        _Source("user_prefs", ("water_model", "water")),
    ),
    "box_type": (
        _Source("tutorial", ("box_type",)),
        _Source("config.box", ("type",)),
        _Source("locked", ("box_type",)),
        _Source("user_prefs", ("box_type",)),
    ),
    # No user_prefs source below: only forcefield, water and box_type are ever
    # written to meta.json["user_preferences"], so listing the others would be
    # dead spec.
    "box_distance_nm": (
        _Source("tutorial", ("box_distance_nm",)),
        _Source("config.box", ("edge_distance_nm",)),
        _Source("locked", ("box_distance_nm",)),
    ),
    "ion_concentration_M": (
        _Source("config.ions", ("concentration_M",)),
        _Source("locked", ("ion_concentration_M",)),
    ),
    "neutralize": (
        _Source("config.ions", ("neutralize",)),
        _Source("locked", ("neutralize",)),
    ),
}

# Used only when no layer supplies the key at all.
FALLBACKS: dict[str, Any] = {
    "forcefield": "charmm36",
    "water_model": "tip3p",
    "box_type": "cubic",
    "box_distance_nm": 1.0,
    "ion_concentration_M": 0.15,
    "neutralize": True,
}


def _supplied(mapping: Any, keys: tuple[str, ...]) -> tuple[bool, Any]:
    """Return (found, value). A key spelled but left blank counts as unset."""
    if not isinstance(mapping, dict):
        return False, None
    for key in keys:
        if key not in mapping:
            continue
        value = mapping[key]
        if value is None or value == "":
            continue
        return True, value
    return False, None


class Resolved(NamedTuple):
    values: dict[str, Any]
    #: parameter name -> layer that supplied it ("fallback" when none did)
    provenance: dict[str, str]


def resolve(tutorial_defaults: dict[str, Any] | None = None,
            system_config: dict[str, Any] | None = None,
            user_prefs: dict[str, Any] | None = None,
            locked: dict[str, Any] | None = None) -> Resolved:
    """Decide every build parameter and record where each value came from."""
    config = system_config or {}
    layers: dict[str, Any] = {
        "tutorial": tutorial_defaults or {},
        "config.forcefield": config.get("forcefield") or {},
        "config.box": config.get("box") or {},
        "config.ions": config.get("ions") or {},
        "locked": locked or {},
        "user_prefs": user_prefs or {},
    }

    values: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for name, sources in _SPEC.items():
        values[name] = FALLBACKS.get(name)
        provenance[name] = "fallback"
        for source in sources:
            found, value = _supplied(layers[source.layer], source.keys)
            if found:
                values[name] = value
                provenance[name] = source.layer
    return Resolved(values=values, provenance=provenance)


def locked_settings(tutorial_defaults: dict[str, Any] | None = None,
                    system_config: dict[str, Any] | None = None,
                    user_prefs: dict[str, Any] | None = None) -> dict[str, Any]:
    """The parameter block recorded in the run plan and protocol contract."""
    return resolve(tutorial_defaults, system_config, user_prefs).values


def demo() -> None:
    """Self-check: the precedence rules and the falsy-value handling."""
    defaults = {"forcefield": "charmm36", "water_model": "tip3p",
                "box_type": "cubic", "box_distance_nm": 1.0}

    # Nothing configured: the tutorial's own values, then hard fallbacks.
    r = resolve(defaults, {}, {})
    assert r.values["box_distance_nm"] == 1.0, r.values
    assert r.provenance["box_distance_nm"] == "tutorial", r.provenance
    assert r.values["ion_concentration_M"] == 0.15, r.values
    assert r.provenance["ion_concentration_M"] == "fallback", r.provenance

    # The Lysozyme preset: 0 M salt is a real choice and must survive.
    preset = {"forcefield": {"name": "charmm36", "water_model": "tip3p"},
              "box": {"type": "cubic", "edge_distance_nm": 1.2},
              "ions": {"concentration_M": 0.0, "neutralize": True}}
    r = resolve(defaults, preset, {})
    assert r.values["ion_concentration_M"] == 0.0, r.values
    assert r.provenance["ion_concentration_M"] == "config.ions", r.provenance
    assert r.values["box_distance_nm"] == 1.2, r.values
    assert r.provenance["box_distance_nm"] == "config.box", r.provenance

    # A zero box distance is honoured too — this is the bug the old `or` hid.
    r = resolve(defaults, {"box": {"edge_distance_nm": 0}}, {})
    assert r.values["box_distance_nm"] == 0, r.values

    # A blank string means "not set", so the tutorial default still applies.
    r = resolve(defaults, {"forcefield": {"name": ""}}, {})
    assert r.values["forcefield"] == "charmm36", r.values
    assert r.provenance["forcefield"] == "tutorial", r.provenance

    # user_prefs outranks the wizard, including the legacy "water" spelling.
    r = resolve(defaults, preset, {"water": "spce"})
    assert r.values["water_model"] == "spce", r.values
    assert r.provenance["water_model"] == "user_prefs", r.provenance

    # False is a value, not an absence.
    r = resolve(defaults, {"ions": {"neutralize": False}}, {})
    assert r.values["neutralize"] is False, r.values
    assert r.provenance["neutralize"] == "config.ions", r.provenance

    # The builder layers the contract's locked block over the raw config, and
    # legacy user_prefs still outrank it (this is the builder's old ordering).
    r = resolve(defaults, preset, {}, locked={"box_distance_nm": 1.4})
    assert r.values["box_distance_nm"] == 1.4, r.values
    assert r.provenance["box_distance_nm"] == "locked", r.provenance
    # A locked concentration of 0 must not fall back to 0.15.
    r = resolve(defaults, {}, {}, locked={"ion_concentration_M": 0})
    assert r.values["ion_concentration_M"] == 0, r.values
    assert r.provenance["ion_concentration_M"] == "locked", r.provenance

    print("run_parameters demo OK")


if __name__ == "__main__":
    demo()
