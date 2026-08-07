"""Guards against the frontend's recurring failure mode.

index.html is a single hand-edited file with no build step, so nothing catches
a `getElementById` that points at markup somebody deleted. That has bitten this
project twice: a rollback restored the xterm terminal's JavaScript without its
container div, and a removed 3D minimap widget left behind functions that threw
`TypeError` on a null stage. Both failures were silent -- the exception escaped
mid-function and skipped every later statement, so the UI simply stopped
updating with no visible error.

These tests read the file as text; they need no browser and no npm.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parent.parent / "web" / "static" / "index.html"

# Elements that legitimately may not exist: optional markup whose call sites
# are all null-guarded. Add to this only alongside a verified `if (el)` guard.
KNOWN_OPTIONAL = {
    "expert-toggle",   # advanced wizard panel; guarded by `if (expToggle)`
    "lb-next-3-btn",   # ligand-builder step 3 button is missing from the
                       # markup (separate pre-existing gap); guarded by
                       # `if (lbNext)` so it no longer throws.
}


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def element_ids(html: str) -> set[str]:
    return set(re.findall(r'\sid="([^"]+)"', html))


def test_every_getelementbyid_target_exists(html: str, element_ids: set[str]) -> None:
    refs = set(re.findall(r"getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)", html))
    dangling = sorted(refs - element_ids - KNOWN_OPTIONAL)
    assert not dangling, (
        "JavaScript references element ids that do not exist in the markup: "
        f"{dangling}. Either restore the markup or delete the dead code."
    )


def test_run_view_tabs_are_wired_both_ways(html: str, element_ids: set[str]) -> None:
    """switchRunTab() builds ids by template, so a typo cannot be grepped."""
    tabs = re.search(r"const RUN_TABS = \[([^\]]+)\]", html)
    assert tabs, "RUN_TABS list not found -- did the tab implementation change?"
    names = re.findall(r"'([a-z]+)'", tabs.group(1))
    assert names, "RUN_TABS parsed empty"
    for name in names:
        assert f"run-tab-{name}" in element_ids, f"missing tab button for '{name}'"
        assert f"run-pane-{name}" in element_ids, f"missing tab panel for '{name}'"


def test_metric_rail_ids_all_receive_values(html: str, element_ids: set[str]) -> None:
    """Every rail slot must be written by the parser.

    A slot with markup but no writer renders a permanent em dash, which is what
    the old Temp/Pressure tile did -- runner.log never contains that data.
    """
    rail_ids = {i for i in element_ids if i.startswith("metric-")}
    assert rail_ids, "no metric rail elements found"
    written = set(re.findall(r"set\('(metric-[a-z]+)'", html))
    orphans = sorted(rail_ids - written)
    assert not orphans, f"metric slots that nothing ever populates: {orphans}"


def test_no_undeclared_el_or_match_identifiers(html: str) -> None:
    """Catches the exact bug that broke selectRun: using `perfEl`/`perfMatch`
    without declaring them raises ReferenceError, not undefined."""
    script = max(
        re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", html, re.S),
        key=len,
    )
    # Names that exist for the whole script: function declarations and globals.
    script_scope = set(re.findall(r"function\s+(\w+)", script))
    script_scope |= set(re.findall(r"^\s*(?:const|let|var)\s+(\w+)", script, re.M))

    for match in re.finditer(r"function\s+(\w+)\s*\(([^)]*)\)\s*\{", script):
        name, params = match.group(1), match.group(2)
        body = script[match.end() : match.end() + 4000]
        declared = set(script_scope)
        declared |= set(re.findall(r"\b(\w+)", params))
        declared |= set(re.findall(r"\b(?:const|let|var)\s+(\w+)", body))
        # arrow-function params, both `x =>` and `(x, y) =>`
        for arrow in re.findall(r"\(?([\w\s,]+?)\)?\s*=>", body):
            declared |= set(re.findall(r"\b(\w+)", arrow))
        used = set(
            re.findall(r"\b(\w+(?:El|Match|Matches|Btn))\b(?=\s*(?:&&|\.|\[|\)))", body)
        )
        undeclared = sorted(u for u in used if u not in declared)
        assert not undeclared, (
            f"function {name}() reads undeclared identifier(s) "
            f"{undeclared} -- this throws ReferenceError at runtime"
        )


def test_no_latex_math_in_markup(html: str) -> None:
    """Nothing renders MathJax here, so `$F_{\\max}$` prints literal dollars.

    Only body markup is scanned: JavaScript template literals (`${...}`) are
    full of dollar-brace pairs that are not math.
    """
    markup = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    markup = re.sub(r"<style.*?</style>", "", markup, flags=re.S)
    found = re.findall(r"\$[^$\n]{0,40}?[\\_^{][^$\n]{0,40}?\$", markup)
    assert not found, f"LaTeX math found in markup: {found}. Write it as plain text."
