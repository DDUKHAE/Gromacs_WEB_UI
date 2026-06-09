# Analysis

## Correcting for Periodicity Effects

Now that we have simulated our protein, we should run some analysis on the system. What types of data are important? This is an important question to ask before running the simulation, so you should have some ideas about the types of data you will want to collect in your own systems. For this tutorial, a few basic tools will be introduced.

The first is `trjconv`, which is used as a post-processing tool to strip out coordinates, correct for periodicity, or manually alter the trajectory (time units, frame frequency, etc). For this exercise, we will use `trjconv` to account for any periodicity in the system. The protein will diffuse through the unit cell, and may appear "broken" or may "jump" across to the other side of the box. To account for such behaviors, issue the following:

```bash
gmx trjconv -s md_0_10.tpr -f md_0_10.xtc -o md_0_10_noPBC.xtc -pbc mol -center
```

Select 1 ("Protein") as the group to be centered and 0 ("System") for output. We will conduct all our analyses on this "corrected" (more formally, "reimaged") trajectory.

## Root-Mean-Square Deviation

Let's look at structural deviations first. GROMACS has a built-in utility for RMSD calculations called `rms`. To use `rms`, issue this command:

```bash
gmx rms -s md_0_10.tpr -f md_0_10_noPBC.xtc -o rmsd.xvg -tu ns
```

Choose 4 ("Backbone") for both the least-squares fit and the group for RMSD calculation. The `-tu` flag will output the results in terms of ns, even though the frames in the trajectory were written with time stamps in ps. This is done for clarity of the output (especially if you have a long simulation - "1e+05 ps" does not look as nice as "100 ns"). The output plot will show the RMSD relative to the structure present in the minimized, equilibrated system.

If we wish to calculate RMSD relative to the crystal structure, we could issue the following `gmx rms` command. Recall that the coordinates stored in `em.tpr` are the un-minimized, solvated system, so the protein coordinates are those taken directly from the 1AKI PDB entry, with added hydrogen atoms (which are not used for the RMSD calculation, anyway).

```bash
gmx rms -s em.tpr -f md_0_10_noPBC.xtc -o rmsd_xtal.xvg -tu ns
```

Plotted together, results look something like:

![RMSD](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_md_rmsd.png)

The raw data (gray and pink points) have been smoothed over a 500-ps (50-frame) window using the "Running Averages" feature in XmGrace (solid lines). This option is invoked by selecting Data -> Transformations -> Running Averages, then selecting the data set(s) to generate the smoothed windows, and the window length.

Both time series show the RMSD fluctuates around an average of 0.09 ± 0.01 nm (0.9 Å), indicating that the structure does not change very much. Subtle differences between the plots indicate that the structure at t = 0 ns is slightly different from this crystal structure. This is to be expected, since it has been energy-minimized, and because the position restraints are not 100% perfect, as discussed previously. Note that RMSD cannot be used as a metric to assess convergence of the simulation or determine "stability" of a system because it is a degenerate metric of structural change, and it is an extrinsic quantity. A large protein complex may have a 1.0-nm RMSD (10x higher than our result here) but be fairly invariant; the quantity is simply an accumulation of potentially very small deviations.

## Analyzing Compactness: Rg

The radius of gyration of a protein is a measure of its compactness. If a protein is stably folded, it will likely maintain a relatively steady value of Rg. If a protein unfolds, its Rg will change over time. Let's analyze the radius of gyration for lysozyme in our simulation:

```bash
gmx gyrate -s md_0_10.tpr -f md_0_10_noPBC.xtc -o gyrate.xvg -sel Protein -tu ns
```

![Radius of Gyration](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_md_rg.png)

We can see from the reasonably invariant Rg values (1.409 ± 0.008 nm) that the protein does not undergo any substantial elongation or compaction relative to its starting structure. Thus, it remains in its compact (folded) form over the course of 10 ns at 298 K. This result is not unexpected, but illustrates an advanced capacity of GROMACS analysis that comes built-in. As with the RMSD plot on the previous page, the data have been smoothed over 500-ps running windows in XmGrace.

## Secondary Structure

Protein structure is often assessed in terms of secondary structure, that is, the persistence of α-helices, β-sheets, etc. The GROMACS program `gmx dssp` invokes the Dictionary of Secondary Structure of Proteins (DSSP) algorithm to assign secondary structure to each residue in the protein. To run this analysis, execute the following command:

```bash
gmx dssp -s md_0_10.tpr -f md_0_10_noPBC.xtc -tu ns -o dssp.dat -num dssp_num.xvg
```

After making some adjustments to labeling (there are misformatted characters in the output of version 2025.2) and reordering the data series, one can obtain a plot similar to the following in XmGrace from `dssp_num.xvg`. The solid lines again correspond to a 500-ps (50-frame) running average to smooth fluctuations.

![Secondary Structure](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_md_dssp.png)

## Hydrogen Bonds

GROMACS uses two criteria to determine if a hydrogen bond exists between two groups: (1) the donor-H distance (defaults to 0.35 nm or less, can be tuned with `-hbr`) and (2) the donor-acceptor-H angle (defaults to 30°, can be tuned with `-hba`). Note the order of atoms in the angle criterion; GROMACS does not use the donor-H-acceptor angle as is employed in other software. Hydrogen bonds are highly directional and are strongest when linear, so the use of donor-acceptor-H ≤ 30° means that donor-H-acceptor angles will range from 150° - 180°.

The user is prompted for two selections when computing hydrogen bonds. These groups must be either identical or completely distinct (no shared atoms). Several examples are illustrated below. The first is the number of hydrogen bonds within the backbone of the protein.

```bash
gmx hbond -s md_0_10.tpr -f md_0_10_noPBC.xtc -tu ns -num hbnum_mainchain.xvg
```

Select the "MainChain+H" group (7) for both selections when prompted. In GROMACS, the "MainChain" group contains the N, Cα, C, and O atoms. "MainChain+H" includes those four atoms, plus the amide H atom, which is required for assignment of hydrogen bonds. In GROMACS convention, "Backbone" contains only N, Cα, and C atoms; no hydrogen bonds can be computed from this group, despite the vernacular of "backbone hydrogen bonds."

Next, compute hydrogen bonds formed among sidechain atoms:

```bash
gmx hbond -s md_0_10.tpr -f md_0_10_noPBC.xtc -tu ns -num hbnum_sidechain.xvg
```

Select the "SideChain" group (8) for both selections.

Finally, we will compute hydrogen bonds between the protein and water:

```bash
gmx hbond -s md_0_10.tpr -f md_0_10_noPBC.xtc -tu ns -num hbnum_prot_wat.xvg
```

Select "Protein" (1) and "Water" (12) or "SOL" (13) as the two groups ("Water" and "SOL" are equivalent).

Plotted together, the results should resemble what is shown below:

![Hydrogen Bonds](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_md_hbonds.png)

In each case, the number of hydrogen bonds is relatively consistent over time, which is to be expected in the case of a short simulation like this one. Lysozyme forms a large number of hydrogen bonds with water, roughly 55 within the "backbone" (MainChain+H), and fewer (~20) among sidechain atoms.

## Summary

You have now conducted a molecular dynamics simulation with GROMACS, and analyzed some of the results. This tutorial should not be viewed as comprehensive. There are many more types of simulations that one can conduct with GROMACS (free energy calculations, non-equilibrium MD, and normal modes analysis, just to name a few). You should also review the literature and the GROMACS manual for adjustments to the `.mdp` files provided here for efficiency and accuracy purposes.

If you have suggestions for improving this tutorial, if you notice a mistake, or if anything is otherwise unclear, please feel free to email me. Please note: this is not an invitation to email me for GROMACS problems. I do not advertise myself as a private tutor or personal help service. That's what the GROMACS User Forum is for. I may help you there, but only in the context of providing service to the community as a whole, not just the end user.
