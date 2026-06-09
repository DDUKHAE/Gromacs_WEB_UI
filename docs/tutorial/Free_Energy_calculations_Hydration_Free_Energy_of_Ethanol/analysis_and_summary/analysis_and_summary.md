# Analysis

The `bar` module of GROMACS makes the calculation of ΔG_AB very simple. Simply collect all of the `md*.xvg` files that were produced by `mdrun` (one for each value of λ) in the working directory and run `gmx bar`:

```bash
gmx bar -f Lambda_*/Production_MD/md*.xvg -o -oi
```

The program will print lots of useful information to the screen, in addition to producing three output files: `bar.xvg`, `barint.xvg`, and `histogram.xvg`. The screen output from `gmx bar` should look something like:

```text
Final results in kJ/mol:

point  0 -  1,   DG  6.26 +/-  0.02
...
point 29 - 30,   DG -0.41 +/-  0.01

total  0 - 30,   DG 17.80 +/-  0.20
```

The value of ΔG_AB obtained is 17.80 ± 0.20 kJ mol^-1, or 4.25 ± 0.05 kcal mol^-1. Since the process conducted for this demonstration was the transformation of ethanol into a dummy molecule, the reverse process (the introduction of uncharged ethanol into water, thus the actual hydration free energy of the process) corresponds to a ΔG_AB of -4.25 ± 0.05 kcal mol^-1 (assuming reversibility).

This value differs slightly from the experimental value of -5.01 kcal mol^-1 and the value of -5.34 ± 0.12 kcal mol^-1 previously reported with CHARMM22. Deviations are likely due to the fact that the topology used here came from the CGenFF parameter set, rather than the ethanol model compound optimized for the CHARMM protein force field; there are minor differences in partial charge assignments and Lennard-Jones parameters of the constitutent atom types.

# Summary

In this exercise, you calculated the free energy of hydration for ethanol in water (technically, the reverse of this process, but it's just a matter of flipping the sign, though you may want to demonstrate this on your own as a test of your skills!).
