from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path


def is_propka_available() -> bool:
    return shutil.which("propka3") is not None or shutil.which("propka") is not None


def run_propka(pdb_path: str | Path, ph: float = 7.0) -> dict:
    """Run PROPKA on a PDB file. Returns structured protonation result.

    When PROPKA is not installed, returns {"available": False, ...} as graceful fallback.
    """
    if not is_propka_available():
        return {"available": False, "his_states": {}, "pka_list": []}

    pdb_path = Path(pdb_path)
    cmd = shutil.which("propka3") or shutil.which("propka")

    with tempfile.TemporaryDirectory() as tmpdir:
        import shutil as sh
        tmp_pdb = Path(tmpdir) / pdb_path.name
        sh.copy(pdb_path, tmp_pdb)

        proc = subprocess.run(
            [cmd, str(tmp_pdb)],
            capture_output=True, text=True, cwd=tmpdir,
        )

        pka_file = Path(tmpdir) / tmp_pdb.with_suffix(".pka").name
        if not pka_file.exists():
            return {"available": True, "his_states": {}, "pka_list": [], "error": proc.stderr[:500]}

        return _parse_propka_output(pka_file.read_text(), ph)


def _parse_propka_output(pka_text: str, ph: float) -> dict:
    """Parse PROPKA .pka output text into structured dict."""
    pka_list: list[dict] = []
    his_states: dict[str, str] = {}

    in_summary = False
    for line in pka_text.splitlines():
        if "SUMMARY OF THIS PREDICTION" in line:
            in_summary = True
            continue
        if in_summary and line.strip().startswith("---"):
            if pka_list:  # second --- means end of summary
                break
            continue
        if in_summary and line.strip():
            parts = line.split()
            if len(parts) >= 4:
                resname, resseq, chain = parts[0], parts[1], parts[2]
                try:
                    pka_value = float(parts[3])
                except ValueError:
                    continue
                pka_list.append({"resname": resname, "resseq": resseq, "chain": chain, "pka": pka_value})
                if resname == "HIS":
                    state = "HSP" if pka_value > ph else "HSD"
                    his_states[f"{chain}:{resseq}"] = state

    return {"available": True, "his_states": his_states, "pka_list": pka_list}
