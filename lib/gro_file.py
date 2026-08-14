"""Reading, writing and concatenating GROMACS `.gro` coordinate files.

Format, as produced by gmx:

    line 1      free-text title
    line 2      number of atoms, right-aligned
    lines 3..   one fixed-column line per atom
    last line   three box vectors

This module exists because the KALP-15/DPPC tutorial's merge step is `cat`
followed by hand-editing — "remove unnecessary lines (the box vectors from the
KALP structure, the header information from the DPPC structure) and update the
second line of the coordinate file (total number of atoms) accordingly" — and
that arithmetic has to be exact.

Atom lines are treated as opaque strings. The residue-number and atom-number
fields are five characters wide and wrap modulo 100000, so re-emitting them
from parsed integers would corrupt any system at or above that size. Nothing
here needs their numeric values.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class GroFileError(Exception):
    pass


@dataclass
class Gro:
    title: str
    atoms: list[str]
    box: str


def read(path: Path) -> Gro:
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 3:
        raise GroFileError(f"{path} has {len(lines)} lines; a .gro needs at least 3")
    try:
        declared = int(lines[1].strip())
    except ValueError as exc:
        raise GroFileError(f"{path} line 2 is not an atom count: {lines[1]!r}") from exc
    atoms = lines[2:-1]
    if len(atoms) != declared:
        raise GroFileError(
            f"{path} declares {declared} atoms but carries {len(atoms)} atom lines"
        )
    return Gro(title=lines[0].strip(), atoms=atoms, box=lines[-1])


def write(path: Path, gro: Gro) -> None:
    body = [gro.title, f"{len(gro.atoms):5d}", *gro.atoms, gro.box]
    Path(path).write_text("\n".join(body) + "\n", encoding="utf-8")


def count(path: Path) -> int:
    """The atom count a file declares on line 2."""
    with Path(path).open(encoding="utf-8", errors="replace") as handle:
        handle.readline()
        try:
            return int(handle.readline().strip())
        except ValueError as exc:
            raise GroFileError(f"{path} line 2 is not an atom count") from exc


def concat(a: Gro, b: Gro, title: str) -> Gro:
    """Append `b`'s atoms to `a`'s, keeping `b`'s box.

    `b` is the bilayer: the combined system adopts its unit cell, which is what
    the tutorial means by discarding the peptide's box vectors.
    """
    return Gro(title=title, atoms=[*a.atoms, *b.atoms], box=b.box)


def box_vectors(gro: Gro) -> tuple[float, float, float]:
    parts = gro.box.split()
    if len(parts) < 3:
        raise GroFileError(f"box line has {len(parts)} fields, need at least 3: {gro.box!r}")
    x, y, z = (float(v) for v in parts[:3])
    return x, y, z
