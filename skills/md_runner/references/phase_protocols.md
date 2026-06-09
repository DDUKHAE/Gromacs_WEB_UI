# Phase Protocols

| Variant | Phase sequence |
|---|---|
| protein_aqueous_standard | em → nvt → npt → production |
| membrane_md_standard | em → nvt → npt → npt → production |
| protein_ligand_complex | em → nvt → npt → production |
| umbrella_sampling | em → nvt → npt → umbrella (per window) |
| free_energy_alchemical | em → nvt → npt → free_energy (per lambda) |
| biphasic_system | em → nvt → npt → production |
| virtual_sites_topology | em → production |

Per-phase defaults live in `lib/mdp_templates/base.py`. Override via
the `phase_overrides` field of `run_simulation`.
