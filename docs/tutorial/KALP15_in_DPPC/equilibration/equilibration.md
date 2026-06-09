# Equilibration

Equilibration will be conducted much like in the case of a solvated protein. Generally a short NVT equilibration phase is followed by a longer NPT phase. The reason for this procedure is that we are now dealing with a heterogenous system, with both water and DPPC acting as solvent. Such heterogeneity requires a longer equilibration process. Water has to re-orient around the lipid headgroups and any exposed parts of the protein, and the lipids have to orient themselves around the protein as well. Such processes take some time, and lipid equilibration may take several ns of simulation time.

## Part 1: NVT Equilibration

For membrane protein simulations, we will need to create a special index group consisting of protein and lipids. To do this, use `make_ndx`:

```bash
gmx make_ndx -f em.gro -o index.ndx
```
Entering `1 | 13` at the `make_ndx` prompt merges the Protein (1) and DPPC (13) groups. This new group will be used for center-of-mass motion removal and temperature coupling.

We will start with NVT, calling `grompp` and `mdrun` just as we did at the EM step:

```bash
gmx grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -n index.ndx -o nvt.tpr
gmx mdrun -deffnm nvt
```

Most of the parameters we are using are comparable to those in the lysozyme tutorial, with a few changes:

*   **`rcoulomb`, `rvdw` = 1.2**: We are using a 1.2-nm short-range cutoff for electrostatics, and van der Waals interactions. The Berger lipids were parametrized with a 1.0-nm cutoff and GROMOS96 with 0.9 nm for electrostatics and 1.4 nm for van der Waals interactions. The value used here has been employed and verified to produce reasonable physical behavior.
*   **`ref_t`, `gen_temp` = 323**: We must use a temperature that is above the phase transition temperature of the lipid. For DPPC, 323 K is commonly used.
*   **`tc-grps` = Protein_DPPC Water_and_ions**: The two groups are coupled separately due to the different rates of diffusion of the two phases.
*   **`comm-grps`**: A new section pertaining to center-of-mass (COM) motion removal. Since interfacial systems have a tendency to move laterally, the motion of the bilayer COM and solvent COM must be reset separately.

Use `gmx energy` to confirm that the temperature of the system has stabilized at 323 K before continuing.

## Part 2: NPT Equilibration

Now that the temperature is stable, we must equilibrate with respect to pressure. The NPT phase for a membrane protein system is generally somewhat longer than for a simple aqueous protein, again due to the heterogeneity of the system. Here, we will conduct a 1-ns NPT equilibration.

There are a few changes in this `.mdp` file worth noting:

*   **`tcoupl` = Nose-Hoover**: The Nosé-Hoover thermostat is widely used in membrane simulations because it produces a correct kinetic ensemble and allows for fluctuations that produce more natural dynamics.
*   **`pcoupltype` = semiisotropic**: Uniform pressure scaling (isotropic) is not appropriate for membranes. A bilayer should be allowed to deform in the x-y plane independently of the z-axis.
*   There are now two values specified for both compressibility and `ref_p`, corresponding to values for the x-y and z dimensions, respectively.

Now, proceed with `grompp` and `mdrun`, as usual:

```bash
gmx grompp -f npt.mdp -c nvt.gro -r nvt.gro -t nvt.cpt -p topol.top -n index.ndx -o npt.tpr
gmx mdrun -deffnm npt
```

Analyze the pressure progression, again using `gmx energy`. It is also advisable to verify that the box vectors have stabilized, ensuring a stable lateral area of the membrane (Box-X and Box-Y).
