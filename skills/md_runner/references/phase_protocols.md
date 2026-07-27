# Phase Protocols

| Variant | Phase sequence |
|---|---|
| protein_aqueous_standard | em → nvt → npt (Berendsen) → npt_pr (Parrinello–Rahman) → production |
| membrane_md_standard | em → nvt → npt (Berendsen) → npt_pr (Parrinello–Rahman) → production |
| protein_ligand_complex | em → nvt → npt (Berendsen) → npt_pr (Parrinello–Rahman) → production |
| umbrella_sampling | em → nvt → npt (Berendsen) → npt_pr (Parrinello–Rahman) → umbrella (per window) |
| free_energy_alchemical | em → nvt → npt (Berendsen) → npt_pr (Parrinello–Rahman) → free_energy (per lambda) |
| biphasic_system | em → nvt → npt (Berendsen) → npt_pr (Parrinello–Rahman) → production |
| virtual_sites_topology | em → production |

Per-phase defaults live in `lib/mdp_templates/base.py`. Override via
the `phase_overrides` field of `run_simulation`.

`npt` and `npt_pr` deliberately use distinct output names. This preserves the
Berendsen-relaxed coordinate as an auditable artifact and makes resume logic
unable to mistake one completed NPT stage for both of them.
