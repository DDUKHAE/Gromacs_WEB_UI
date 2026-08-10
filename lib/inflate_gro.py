"""Running the KALP-15/DPPC tutorial's two perl helpers.

`inflategro.pl` scales lipid positions in x-y, drops the lipids that overlap the
protein, and reports the resulting area per lipid. `water_deletor.pl` removes
water that `solvate` drove into the hydrophobic core.

Area per lipid is read from the `.dat` file the script writes, documented in its
own usage text as "3 area per lipid values: total, upper leaflet & lower
leaflet" and verified to be one line of three whitespace-separated floats. The
deleted-lipid counts have no file, so they come from stdout -- confirmed by
running inflategro.pl on the real tracked KALP-15 + DPPC-128 system, which
printed "7 lipids within cut-off range... 0 will be removed from the upper
leaflet... 7 will be removed from the lower leaflet...".
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lib import gro_file


class InflateGroError(Exception):
    pass


_REMOVED_RE = re.compile(
    r"(\d+)\s+will be removed from the (upper|lower) leaflet", re.IGNORECASE
)


@dataclass
class InflateResult:
    apl_total: float
    apl_upper: float
    apl_lower: float
    removed_upper: int
    removed_lower: int
    output: Path
    area_dat: Path

    @property
    def removed(self) -> int:
        return self.removed_upper + self.removed_lower


def parse_area_dat(path: Path) -> tuple[float, float, float]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    parts = text.split()
    if len(parts) < 3:
        raise InflateGroError(
            f"{path} holds {len(parts)} fields; expected 3 values "
            f"(total, upper, lower): {text!r}"
        )
    total, upper, lower = (float(v) for v in parts[:3])
    return total, upper, lower


def parse_removed(stdout: str) -> tuple[int, int]:
    """Lipids removed from each leaflet.

    The messages are printed only when lipids actually overlap the protein, so
    their absence means none were removed, not that parsing failed.
    """
    found = {leaflet.lower(): int(n) for n, leaflet in _REMOVED_RE.findall(stdout)}
    return found.get("upper", 0), found.get("lower", 0)


def _run_perl(script: Path, args: list[str], cwd: Path) -> str:
    script = Path(script)
    if not script.is_file():
        raise InflateGroError(f"perl script not found: {script}")
    perl = shutil.which("perl")
    if perl is None:
        raise InflateGroError("perl is not installed")
    proc = subprocess.run(
        [perl, str(script), *args], cwd=str(cwd),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise InflateGroError(
            f"{script.name} exited {proc.returncode}: {proc.stderr[-600:]}"
        )
    return proc.stdout


def inflate(script: Path, gro: Path, scale: float, resname: str, cutoff_a: int,
            out: Path, gridsize: int, area_dat: Path, cwd: Path) -> InflateResult:
    """Scale lipid positions in x-y and report area per lipid.

    `cutoff_a` is in angstroms: only lipids whose P-CA distance exceeds it are
    written, which is how lipids overlapping the protein get dropped. The
    tutorial uses 14 for the initial inflation and 0 while shrinking.
    """
    stdout = _run_perl(
        script,
        [str(gro), str(scale), resname, str(cutoff_a), str(out),
         str(gridsize), str(area_dat)],
        cwd,
    )
    if not Path(out).is_file():
        raise InflateGroError(
            f"{Path(script).name} wrote no output at {out}; stdout tail: "
            f"{stdout[-600:]}"
        )
    if not Path(area_dat).is_file():
        raise InflateGroError(f"{Path(script).name} wrote no area file at {area_dat}")
    total, upper, lower = parse_area_dat(area_dat)
    removed_upper, removed_lower = parse_removed(stdout)
    return InflateResult(
        apl_total=total, apl_upper=upper, apl_lower=lower,
        removed_upper=removed_upper, removed_lower=removed_lower,
        output=Path(out), area_dat=Path(area_dat),
    )


def delete_trapped_water(script: Path, gro: Path, out: Path, cwd: Path,
                          ref: str = "O33", middle: str = "C50",
                          nwater: int = 3) -> int:
    """Remove water inside the bilayer, returning the number of atoms dropped.

    Defaults are the tutorial's: O33 as the reference lipid atom, C50 as the
    marker for the bilayer midplane, 3 atoms per water for SPC.
    """
    before = gro_file.count(gro)
    _run_perl(
        script,
        ["-in", str(gro), "-out", str(out), "-ref", ref,
         "-middle", middle, "-nwater", str(nwater)],
        cwd,
    )
    if not Path(out).is_file():
        raise InflateGroError(f"{Path(script).name} wrote no output at {out}")
    return before - gro_file.count(out)
