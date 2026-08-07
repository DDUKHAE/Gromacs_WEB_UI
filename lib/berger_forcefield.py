"""Build the GROMOS53a6 + Berger-lipid force field the KALP-15/DPPC run needs.

The membrane tutorial has you hand-edit a copy of `$GMXLIB/gromos53a6.ff` to
absorb the Berger lipid parameters from `lipid.itp`
(``docs/tutorial/KALP15_in_DPPC/generate_topology/modify_the_topology.md``).
That is six mechanical edits, so it is done here instead:

1. copy ``gromos53a6.ff`` to ``gromos53a6_lipid.ff``
2. merge ``lipid.itp``'s ``[atomtypes]`` into ``ffnonbonded.itp``, adding the
   ``at.num`` column that ``lipid.itp`` omits
3. merge ``[nonbond_params]``, dropping the lipid-GROMOS block so protein-lipid
   interactions come from the GROMOS combination rules instead
4. drop the ``HW`` rows that survive in the kept SPC block
5. merge ``[pairtypes]`` into ``ffnonbonded.itp``
6. append ``[dihedraltypes]`` to ``ffbonded.itp``

Three details bite anyone doing this by hand or with a naive script:

* ``at.num`` cannot be derived by rounding the mass. Berger is a united-atom
  field, so CH2 has mass 14.0270 while nitrogen has 14.0067 — both round to 14,
  but one is carbon and the other nitrogen. The mapping below is explicit.
* ``lipid.itp`` misspells the marker as ``;; paramaters for lipid-GROMOS
  interactions``. Matching the tutorial's spelling finds nothing and silently
  keeps parameters that must be removed, so the match is on ``lipid-GROMOS``.
* Most ``HW`` rows live in the SPC block the tutorial says to *keep*, so step 4
  is not made redundant by step 3. Their c6/c12 are all zero, which is why
  deleting them equals the tutorial's alternative of renaming ``HW`` to ``H``.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

FF_SOURCE = "gromos53a6"
FF_TARGET = "gromos53a6_lipid"

#: Berger atom type mass -> atomic number. United-atom masses (CH, CH2, CH3)
#: all resolve to carbon; see the module docstring.
_MASS_TO_ATOMIC_NUMBER: dict[str, int] = {
    "30.9738": 15,  # P
    "15.9994": 8,   # O
    "15.0350": 6,   # CH3
    "14.0270": 6,   # CH2
    "14.0067": 7,   # N
    "13.0190": 6,   # CH
    "12.0110": 6,   # C
}

#: Partners a lipid type may legitimately keep in a prepared [nonbond_params]:
#: another Berger type (they all start with L), SPC water, or the ``H`` the
#: tutorial offers as a rename target for ``HW``. Anything else -- C, CA, N, O,
#: S, ZN and the rest of GROMOS -- only appears in the lipid-GROMOS block.
_KEEPABLE_PARTNERS = frozenset({"OW", "HW", "H"})


def _is_lipid_or_solvent(atom_type: str) -> bool:
    return atom_type.startswith("L") or atom_type in _KEEPABLE_PARTNERS


_LIPID_GROMOS_MARKER = re.compile(r";;.*lipid-GROMOS", re.IGNORECASE)
_SPC_MARKER = re.compile(r";;.*lipid-SPC", re.IGNORECASE)
_HW_ROW = re.compile(r"\bHW\b")


class BergerForceFieldError(Exception):
    pass


def _section(text: str, name: str) -> str:
    """Return the body of an .itp section, excluding its own header line."""
    match = re.search(rf"^\[\s*{name}\s*\](.*?)(?=^\[|\Z)", text, re.S | re.M)
    if match is None:
        raise BergerForceFieldError(f"lipid.itp has no [ {name} ] section")
    return match.group(1)


def _data_rows(body: str) -> list[str]:
    return [ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith(";")]


def _has_atomic_number_column(row: str) -> bool:
    """True when an [atomtypes] row already carries at.num in column 2.

    raw lipid.itp:  name mass   charge ptype ...  -> column 2 is a mass, 15.9994
    prepared:       name at.num mass   charge ... -> column 2 is a small integer

    Keying on "bare small integer" is safe here: every mass in the table is
    written with a decimal point, and no atomic number reaches the mass range.
    """
    parts = row.split()
    if len(parts) < 7:
        return False
    return re.fullmatch(r"\d{1,3}", parts[1]) is not None


def _atomtypes_with_atomic_number(body: str) -> list[str]:
    """Return [atomtypes] rows carrying the at.num column gromos requires.

    Accepts lipid.itp either as distributed or already prepared by hand, so a
    workspace whose lipid.itp was edited manually yields the same force field.

    raw:       name mass charge ptype c6 c12 [free-text comment]
    prepared:  name at.num mass charge ptype c6 c12 [free-text comment]
    """
    out: list[str] = []
    for row in _data_rows(body):
        parts = row.split()
        if _has_atomic_number_column(row):
            out.append(row.rstrip())
            continue
        if len(parts) < 6:
            raise BergerForceFieldError(f"unparseable [atomtypes] row: {row.strip()!r}")
        name, mass, charge, ptype, c6, c12 = parts[:6]
        trailing = " ".join(parts[6:])
        atomic = _MASS_TO_ATOMIC_NUMBER.get(mass)
        if atomic is None:
            raise BergerForceFieldError(
                f"no atomic number known for atom type {name!r} of mass {mass}. "
                "Add it to _MASS_TO_ATOMIC_NUMBER — do not guess by rounding, "
                "united-atom masses collide with real element masses."
            )
        line = f"{name:>5} {atomic:>4} {mass:>10} {charge:>8} {ptype:>3} {c6:>14} {c12:>14}"
        if trailing:
            line = f"{line} ; {trailing.lstrip('; ')}"
        out.append(line)
    return out


def _nonbond_params_without_gromos_block(body: str) -> list[str]:
    """Keep the lipid-lipid rows and the SPC block; drop lipid-GROMOS and HW.

    The lipid-GROMOS parameters are removed so that protein-lipid interactions
    fall back to the GROMOS53a6 combination rules, which is the whole point of
    this force field being a "mixture".
    """
    lines = body.splitlines()
    start = next((i for i, ln in enumerate(lines) if _LIPID_GROMOS_MARKER.search(ln)), None)
    spc = next((i for i, ln in enumerate(lines) if _SPC_MARKER.search(ln)), None)

    if start is None:
        # Already prepared by hand: the block is gone. Do not take the missing
        # marker as proof of that — a deleted comment would then silently keep
        # every parameter the tutorial says to remove. Check the rows instead.
        if spc is None:
            raise BergerForceFieldError(
                "[nonbond_params] has neither the lipid-GROMOS block nor the "
                "lipid-SPC block; refusing to guess which rows to drop"
            )
        survivors = sorted({p[1] for p in (ln.split()[:2] for ln in _data_rows(body))
                            if len(p) == 2 and not _is_lipid_or_solvent(p[1])})
        if survivors:
            raise BergerForceFieldError(
                "[nonbond_params] still pairs lipid types with GROMOS types "
                f"{survivors[:8]} but the lipid-GROMOS marker is missing. Restore "
                "the marker or delete those rows; they must not reach the merge."
            )
        kept = lines
    else:
        if spc is None or spc <= start:
            raise BergerForceFieldError(
                "expected the lipid-SPC block to follow the lipid-GROMOS block"
            )
        kept = lines[:start] + lines[spc:]

    # HW carries zero c6/c12, so dropping these rows and the tutorial's
    # alternative of renaming HW to H are equivalent: GROMOS's own H atom type
    # also has zero c6/c12, so the combination rule yields zero either way.
    # Rows already renamed to H are left alone.
    return [ln for ln in kept if ln.strip() and not _HW_ROW.search(ln)]


def _insert_into_section(text: str, section: str, rows: list[str]) -> str:
    """Append rows to the end of an existing section, before the next header."""
    match = re.search(rf"^\[\s*{section}\s*\](.*?)(?=^\[|\Z)", text, re.S | re.M)
    if match is None:
        raise BergerForceFieldError(f"target file has no [ {section} ] section")
    body = match.group(1).rstrip("\n")
    block = "\n".join([body, "", f"; --- Berger lipid parameters ({section}) ---", *rows, ""])
    return text[: match.start(1)] + "\n" + block.lstrip("\n") + "\n" + text[match.end(1):]


def _append_section(text: str, section: str, rows: list[str]) -> str:
    match = re.search(rf"^\[\s*{section}\s*\]", text, re.M)
    if match is None:
        raise BergerForceFieldError(f"target file has no [ {section} ] section")
    return _insert_into_section(text, section, rows)


def ensure_forcefield_include(topol: Path, forcefield: str = FF_TARGET) -> bool:
    """Point topol.top's force-field include at `forcefield`.

    pdb2gmx already writes this line to match its ``-ff`` argument, so for a
    normally built run this is a no-op. It is checked rather than assumed
    because a topology that reached the workspace another way (a prebuilt
    membrane, an imported run) would otherwise be minimised and simulated
    against gromos53a6 without the lipid parameters — silently wrong numbers
    rather than an error.

    Returns True if the line had to be rewritten.
    """
    topol = Path(topol)
    text = topol.read_text(encoding="utf-8", errors="replace")
    want = f'#include "{forcefield}.ff/forcefield.itp"'
    if want in text:
        return False
    patched, n = re.subn(
        r'#include\s+"[\w.+-]*\.ff/forcefield\.itp"', want, text, count=1
    )
    if n == 0:
        raise BergerForceFieldError(
            f"{topol} has no force-field include to redirect to {forcefield}"
        )
    topol.write_text(patched, encoding="utf-8")
    return True


def add_include(topol: Path, include: str) -> bool:
    """Add ``#include "<include>"`` to topol.top ahead of the water topology.

    The tutorial places it "somewhere after the position restraints section for
    the protein", i.e. between the POSRES block and the water include, so the
    moleculetype is defined before ``[ molecules ]`` refers to it. pdb2gmx
    writes the force-field include itself when called with ``-ff``, so that
    substitution needs no editing here — only this one does.

    Returns False when the include is already present, so a resumed run does
    not add it twice.
    """
    topol = Path(topol)
    text = topol.read_text(encoding="utf-8", errors="replace")
    if re.search(rf'^\s*#include\s+"{re.escape(include)}"', text, re.M):
        return False

    block = f'; Include DPPC chain topology\n#include "{include}"\n\n'
    anchor = re.search(r"^; Include water topology\s*$", text, re.M)
    if anchor is None:
        # No water include (e.g. a vacuum topology): fall back to just before
        # [ system ], which still precedes [ molecules ].
        anchor = re.search(r"^\[\s*system\s*\]", text, re.M)
    if anchor is None:
        raise BergerForceFieldError(
            f"cannot find an insertion point for {include} in {topol}"
        )
    topol.write_text(text[: anchor.start()] + block + text[anchor.start():], encoding="utf-8")
    return True


def build(lipid_itp: Path, gmxlib: Path, dest_parent: Path) -> dict[str, Any]:
    """Create ``<dest_parent>/gromos53a6_lipid.ff``.

    `dest_parent` must be the directory GROMACS runs in, because pdb2gmx looks
    for a `.ff` directory in the working directory before consulting GMXLIB.

    Returns a summary of what was merged, for the run record.
    """
    lipid_itp, gmxlib, dest_parent = Path(lipid_itp), Path(gmxlib), Path(dest_parent)
    source = gmxlib / f"{FF_SOURCE}.ff"
    if not source.is_dir():
        raise BergerForceFieldError(f"{FF_SOURCE}.ff not found in GMXLIB: {source}")
    if not lipid_itp.is_file():
        raise BergerForceFieldError(f"lipid.itp not found: {lipid_itp}")

    dest = dest_parent / f"{FF_TARGET}.ff"
    if dest.exists():
        shutil.rmtree(dest)
    dest_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    text = lipid_itp.read_text(encoding="utf-8", errors="replace")
    atomtypes = _atomtypes_with_atomic_number(_section(text, "atomtypes"))
    nonbond = _nonbond_params_without_gromos_block(_section(text, "nonbond_params"))
    # [pairtypes] carries HW rows too -- 14 of them in the distributed file --
    # and the tutorial's step 4 only mentions [nonbond_params]. HW is not an
    # atom type in gromos53a6 (only OW is), so leaving them makes grompp fail
    # with "Unknown atomtype HW". Following the instructions literally does not
    # produce a working force field; the tutorial's alternative of renaming HW
    # to H does, because H *is* defined. Dropping them here is equivalent: all
    # of these rows are zero.
    pairtypes = [r for r in _data_rows(_section(text, "pairtypes"))
                 if not _HW_ROW.search(r)]
    dihedrals = _data_rows(_section(text, "dihedraltypes"))

    nb_path = dest / "ffnonbonded.itp"
    nb = nb_path.read_text(encoding="utf-8", errors="replace")
    nb = _insert_into_section(nb, "atomtypes", atomtypes)
    nb = _insert_into_section(nb, "nonbond_params", nonbond)
    nb = _insert_into_section(nb, "pairtypes", pairtypes)
    nb_path.write_text(nb, encoding="utf-8")

    bond_path = dest / "ffbonded.itp"
    bonded = bond_path.read_text(encoding="utf-8", errors="replace")
    bonded = _append_section(bonded, "dihedraltypes", dihedrals)
    bond_path.write_text(bonded, encoding="utf-8")

    doc = dest / "forcefield.doc"
    doc.write_text(
        "GROMOS96 53A6 force field, extended to include Berger lipid parameters\n",
        encoding="utf-8",
    )

    return {
        "forcefield": FF_TARGET,
        "path": str(dest),
        "source_forcefield": FF_SOURCE,
        "lipid_itp": str(lipid_itp),
        # Parameter rows only. `nonbond` still carries lipid.itp's section
        # comments, which are worth keeping in the output but are not
        # parameters and must not inflate this count.
        "merged": {
            "atomtypes": len(_data_rows("\n".join(atomtypes))),
            "nonbond_params": len(_data_rows("\n".join(nonbond))),
            "pairtypes": len(_data_rows("\n".join(pairtypes))),
            "dihedraltypes": len(_data_rows("\n".join(dihedrals))),
        },
    }
