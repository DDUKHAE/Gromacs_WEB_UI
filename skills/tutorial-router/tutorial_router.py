import json
import os
import sys


def _lower(text):
    return (text or "").lower()


def _exists(path):
    return os.path.exists(path)


def route_tutorial(input_data):
    prompt = _lower(input_data.get("prompt", ""))
    available_manifests = input_data.get("available_manifests", [])

    selected = "Lysozyme_in_water"
    pipeline_variant = "protein_aqueous_standard"
    confidence = 0.9
    required_inputs = ["protein_pdb"]
    missing_inputs = []

    if "ligand" in prompt or "complex" in prompt:
        selected = "Protein_Ligand_Complex"
        pipeline_variant = "protein_ligand_complex"
        confidence = 0.85
        required_inputs = ["protein_pdb", "ligand_structure"]
    elif "membrane" in prompt or "dppc" in prompt:
        selected = "KALP15_in_DPPC"
        pipeline_variant = "membrane_protein_dppc"
        confidence = 0.85
        required_inputs = ["protein_pdb", "membrane_definition"]

    manifest_exists = any(selected in m for m in available_manifests)
    if not manifest_exists:
        return {
            "status": "error",
            "message": f"Manifest not found for selected tutorial: {selected}",
            "selected_tutorial": selected,
            "pipeline_variant": pipeline_variant,
            "confidence": confidence,
        }

    pdb_path = input_data.get("pdb_path")
    if not pdb_path or not _exists(pdb_path):
        missing_inputs.append("protein_pdb")

    return {
        "status": "success",
        "selected_tutorial": selected,
        "pipeline_variant": pipeline_variant,
        "confidence": confidence,
        "required_inputs": required_inputs,
        "missing_inputs": sorted(list(set(missing_inputs))),
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            payload = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                payload = json.load(f)
    else:
        payload = json.loads(sys.stdin.read())

    result = route_tutorial(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
