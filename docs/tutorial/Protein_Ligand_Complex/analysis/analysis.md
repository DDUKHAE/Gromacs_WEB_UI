# Analysis

As in any simulation conducted with periodic boundary conditions, molecules may appear "broken" or may "jump" back and forth across the box. To recenter the protein and rewrap the molecules within the unit cell to recover the desired rhombic dodecahedral shape, invoke `trjconv`:

```bash
gmx trjconv -s md_0_10.tpr -f md_0_10.xtc -o md_0_10_center.xtc -center -pbc mol -ur compact
```

Choose "Protein" for centering and "System" for output.

To extract the first frame (t = 0 ns) of the trajectory, use `trjconv -dump` with the recentered trajectory:

```bash
gmx trjconv -s md_0_10.tpr -f md_0_10_center.xtc -o start.pdb -dump 0
```

For even smoother visualization, it may be beneficial to perform rotational and translational fitting. Execute `trjconv` as follows:

```bash
gmx trjconv -s md_0_10.tpr -f md_0_10_center.xtc -o md_0_10_fit.xtc -fit rot+trans
```

Choose "Backbone" to perform least-squares fitting to the protein backbone, and "System" for output.

## Distance and Hydrogen Bonds

The 2-propylphenol ligand can engage in a hydrogen bond with the Gln102 side chain. The GROMACS `hbond` module can easily be employed to calculate the number of hydrogen bonds between any groups of atoms. For a more detailed look at how the ligand is interacting with Gln102, we will compute the distance between the hydroxyl group of JZ4 and the carbonyl O atom of Gln102. 

```bash
gmx distance -s md_0_10.tpr -f md_0_10_center.xtc -select 'resname "JZ4" and name OAB plus resid 102 and name OE1' -oall
```

The second criterion usually applied in determining the presence of a hydrogen bond is the angle formed among the donor, hydrogen, and acceptor atoms. In the GROMACS `hbond` module, the angle is defined as hydrogen-donor-acceptor, and this angle should be ≤ 30°. To perform this analysis, first create index groups:

```bash
gmx make_ndx -f em.gro -o index.ndx
```
Type: `13 & a OAB | a H12` (creates group 23), then `1 & r 102 & a OE1` (creates group 24), then `23 | 24` and `q`.

Analyze the angle formed by these three atoms using the `angle` module:

```bash
gmx angle -f md_0_10_center.xtc -n index.ndx -ov angle.xvg
```

## Ligand RMSD

We may be interested in quantifying how much the ligand binding pose has changed over the course of the simulation. To compute a heavy-atom RMSD of just JZ4, create a new index group for it:

```bash
gmx make_ndx -f em.gro -n index.ndx
```
Type: `13 & ! a H*` -> `name 26 JZ4_Heavy` -> `q`.

Execute the `rms` module, choosing "Backbone" for least-squares fitting and "JZ4_Heavy" for the RMSD calculation.

```bash
gmx rms -s em.tpr -f md_0_10_center.xtc -n index.ndx -tu ns -o rmsd_jz4.xvg
```

The calculated RMSD should be about 0.1 nm (1 Å), indicating only a very small change in the ligand's position.

## Interaction Energy

To quantify the strength of the interaction between JZ4 and T4 lysozyme, it may be useful to compute the nonbonded interaction energy between these two species. GROMACS has the ability to decompose the short-range nonbonded energies between any number of defined groups. It is important to note that this quantity is NOT a free energy or a binding energy. 

Calculation of an interaction energy is carried out via the `energygrps` keyword in the `.mdp` file. Only compute interaction energies as a part of your analysis, not your dynamics. Create a new `.tpr` file from an `.mdp` file that has `energygrps = Protein JZ4` defined:

```bash
gmx grompp -f ie.mdp -c npt.gro -t npt.cpt -p topol.top -n index.ndx -o ie.tpr
```

Next, invoke `mdrun` with the `-rerun` option to recalculate energies from the existing simulation trajectory:

```bash
gmx mdrun -deffnm ie -rerun md_0_10.xtc -nb cpu
```

Extract the energy terms of interest via the `energy` module. The terms we are interested in are `Coul-SR:Protein-JZ4` and `LJ-SR:Protein-JZ4`.

```bash
gmx energy -f ie.edr -o interaction_energy.xvg
```

## Summary

You have now conducted a molecular dynamics simulation of a protein-ligand complex with GROMACS. This tutorial should not be viewed as comprehensive. There are many more types of simulations that one can conduct with GROMACS. You should also review the literature and the GROMACS manual for adjustments to the `.mdp` files provided here for efficiency and accuracy purposes.
