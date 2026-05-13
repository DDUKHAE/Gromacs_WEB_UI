import json
import os
import sys


def _doc(docs, *keys):
    for key in keys:
        if docs.get(key):
            return docs.get(key)
    return None


def plan_workflow(input_data):
    manifest_path = input_data.get("manifest_path")
    if not manifest_path or not os.path.exists(manifest_path):
        return {"status": "error", "message": f"Manifest not found: {manifest_path}"}

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    docs = manifest.get("documents", {})
    variant = manifest.get("pipeline_variant", "protein_aqueous_standard")

    step1_doc = _doc(docs, "step_1", "step_1_protein")
    step7_doc = _doc(docs, "step_7_production", "step_7_equilibration")
    step1_action = "topology_generation"
    if variant == "protein_ligand_complex":
        step1_action = "protein_and_ligand_topology_generation"
    elif variant == "membrane_protein_dppc":
        step1_action = "membrane_protein_topology_generation"

    workflow = [
        {"step": 0, "action": "preflight_hardware_state_init", "doc": None},
        {"step": 1, "action": step1_action, "doc": step1_doc},
        {"step": 2, "action": "box_definition", "doc": docs.get("step_2")},
        {"step": 3, "action": "solvation", "doc": docs.get("step_3")},
        {"step": 4, "action": "ionization_preparation", "doc": docs.get("step_5")},
        {"step": 5, "action": "ionization", "doc": docs.get("step_5")},
        {"step": 6, "action": "execution_preparation", "doc": docs.get("step_6")},
        {"step": 7, "action": "equilibration_and_production", "doc": step7_doc},
        {"step": 8, "action": "trajectory_analysis", "doc": docs.get("step_8")},
    ]

    return {
        "status": "success",
        "selected_tutorial": manifest.get("id"),
        "pipeline_variant": manifest.get("pipeline_variant"),
        "workflow": workflow,
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

    result = plan_workflow(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
