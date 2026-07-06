from __future__ import annotations

_ATOM_RECORDS = {"ATOM", "HETATM"}


def apply_his_states(pdb_text: str, his_states: dict[str, str]) -> str:
    """Rename HIS residues in PDB ATOM/HETATM records.

    his_states maps "chain:resseq" -> new_residue_name (e.g. "A:42" -> "HSD").
    Only residues currently named "HIS" are modified; other residues are unchanged.
    Residue name occupies columns 18-20 (0-indexed 17:20) in standard PDB format.
    """
    if not his_states:
        return pdb_text

    lines = pdb_text.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        rec = line[:6].strip()
        if rec in _ATOM_RECORDS and len(line) >= 26:
            resname = line[17:20]
            if resname == "HIS":
                chain = line[21]
                resseq = line[22:26].strip()
                key = f"{chain}:{resseq}"
                if key in his_states:
                    new_name = his_states[key][:3]  # HSD, HSE, or HSP
                    line = line[:17] + new_name + line[20:]
        result.append(line)
    return "".join(result)
