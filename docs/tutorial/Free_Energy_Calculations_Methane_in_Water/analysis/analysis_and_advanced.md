# Analysis

The `bar` module of GROMACS makes the calculation of ΔG_AB very simple. Simply collect all of the `md*.xvg` files that were produced by `mdrun` (one for each value of λ) in the working directory and run `gmx bar`:

```bash
gmx bar -f md*.xvg -o -oi
```

The program will print lots of useful information to the screen, in addition to producing three output files: `bar.xvg`, `barint.xvg`, and `histogram.xvg`.

The value of ΔG_AB is printed at the end of the command output. For example, for the decoupling of methane, the value might be `-9.13 ± 0.09 kJ mol-1`. The reverse process (the introduction of uncharged methane into water, thus the actual hydration energy of the process) corresponds to a ΔG_AB of `2.18 ± 0.02 kcal mol-1`.

Technically, this is all we need to do to arrive at our answer, but `gmx bar` also prints a number of useful output files (all of which are optional). Their contents are worth exploring here.

## Output file 1: bar.xvg

`bar.xvg` plots the relative free energy differences for each interval of λ (i.e., between neighboring Hamiltonians). Each point indicates the free energy difference between neighboring values of λ. Thus, the free energy change from λ = 0 to λ = 1 is simply the sum of the free energy changes of each pair of neighboring λ simulations.

## Output file 2: barint.xvg

The `barint.xvg` file plots the cumulative ΔG as a function of λ. In `barint.xvg`, the point at λ = 1 corresponds to the sum of ΔG from λ vector 0 to λ vector 1, as indicated in the screen output.

# Advanced Applications

One common application of calculating free energies is to determine the ΔG of binding between a ligand and a receptor (e.g., a protein). You would need to perform (de)coupling of the ligand in complex with the receptor and in bulk solution, since ΔG is (in this case) the sum of the free energy change of complexation of the ligand and receptor and the free energy of desolvating the ligand:

*   ΔG_bind = ΔG_complexation + ΔG_desolvation
*   ΔG_solvation = -ΔG_desolvation
*   ∴ ΔG_bind = ΔG_complexation - ΔG_solvation

The transformation of a fully-interacting species (e.g., the ligand) into a "dummy" (a set of atomic centers in the configuration of the ligand that does not engage in any nonbonded interactions with its surroundings) requires turning off both van der Waals interactions and Coulombic interactions between the solute of interest and its surrounding environment.

For most small molecules (generically named "LIG" below), it is more sound to approach the (de)coupling sequentially. In version 5.0+, this is very easily done with the new λ vector capabilities:

```gromacs
couple-moltype           = LIG
couple-intramol          = no
couple-lambda0           = none
couple-lambda1           = vdw-q
init_lambda_state        = 0
calc_lambda_neighbors    = 1
vdw_lambdas              = 0.00 0.05 0.10 ... 1.00 1.00 1.00 ... 1.00
coul_lambdas             = 0.00 0.00 0.00 ... 0.00 0.05 0.10 ... 1.00
```

In this case, the λ value for Coulombic interactions is always zero while the λ value for transforming van der Waals interactions changes. Then, the van der Waals interactions are fully on (λ = 1.00) while the Coulombic interactions are gradually turned on. Keeping track of the states to which λ = 0 and λ = 1 correspond is key to this process. In the above case, `couple-lambda0` says interactions are off, while `couple-lambda1` means interactions are on.

## Summary

You have now calculated the free energy change for a simple transformation that has previously been calculated with high precision, the decoupling of van der Waals interactions between a simple solute (uncharged methane) and solvent (water). Hopefully this tutorial will provide you with the understanding necessary to take on more complex systems.
