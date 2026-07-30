# Final Fix Report

## Scope

- Restored HTTP 422 handling for malformed membrane lipid fractions through centralized builder validation.
- Updated user and contributor documentation to match the removed analyses and consolidated phase authority.

## Files changed

- `lib/membrane_builder.py`
- `tests/unit/test_system_config.py`
- `README.md`
- `README.ko.md`
- `CONTRIBUTING.md`

## TDD evidence

- Red: `pytest -q tests/unit/test_system_config.py::test_membrane_build_rejects_missing_lipid_fraction` failed with `KeyError: 'fraction'` from `lib/membrane_builder.py:67`.
- Green: the same command passed after the builder raised `ValueError`; the endpoint returned HTTP 422. The test uses the real `build_membrane` validation and mocks only external tool availability.
- Focused file: `pytest -q tests/unit/test_system_config.py` — `4 passed`, with one third-party TestClient deprecation warning.
- Full suite: `pytest -q` — `137 passed`, with one third-party TestClient deprecation warning.

## Commit

- Implementation: `708d6c5fff4bf1b17093f048d1e6249672743f27` (`fix: preserve membrane composition validation`)

## Self-review

- Missing, non-numeric, non-finite, boolean, negative, and greater-than-one fractions now raise `ValueError` in the centralized builder; existing sum-to-one validation remains unchanged.
- The regression asserts the route’s public HTTP 422 response without replacing builder validation.
- README references no longer name deleted stub functions, and the contributor guide identifies `lib.protocol_contract.PHASE_SEQUENCE_BY_VARIANT` as the single phase-sequence authority.
- No dependencies or simulation execution behavior were changed.
