# Prerequisite Schema for Derived Tutorials

The `prerequisites` field of `build_environment` accepts the following
keys. Required keys depend on tutorial selection (see
`docs/tutorial/tutorial_index.json`).

| Tutorial | Required prerequisite keys |
|---|---|
| Lysozyme_in_water | none |
| KALP15_in_DPPC | `membrane_composition` (e.g., `{"DPPC": 128}`) |
| Protein_Ligand_Complex | `ligand_structure` or `ligand_itp` |
| Umbrella_Sampling | `reaction_coordinate_definition`, `window_schedule_defined` |
| Building_Biphasic_Systems | `phase_components`, `composition_ratio` |
| Free_Energy_*_Methane | `solute_topology`, `lambda_schedule` |
| Free_Energy_*_Ethanol | `solute_topology`, `coulomb_vdw_lambda_schedule` |
| Virtual_Sites | `molecule_topology`, `virtual_site_definition` |

Missing prerequisites cause env-builder to raise
`UnsupportedTutorialError`. The caller should surface the missing
keys to the user and re-invoke with the inputs filled.
