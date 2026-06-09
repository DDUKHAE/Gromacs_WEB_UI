# Umbrella Sampling Simulations

In this example, we will be sampling COM distances from 0.5 - 5.0 nm along the z-axis using roughly 0.2-nm spacing. 

After having identified the initial configurations of the sampling windows, we can now prepare the umbrella sampling simulations. We will need to generate a number of input files in order to conduct each of the necessary simulations. For example, since we have identified 23 configurations along the reaction coordinate, that means we will need 23 different input files for 23 independent simulations. 

Start by running a brief NPT equilibration in each window.
First `grompp` (input `conf*.gro` file names may differ based on your individual SMD simulation outcome):

```bash
gmx grompp -f npt_umbrella.mdp -c conf6.gro -p topol.top -r conf6.gro -n index.ndx -o npt0.tpr
...
gmx grompp -f npt_umbrella.mdp -c conf449.gro -p topol.top -r conf449.gro -n index.ndx -o npt22.tpr
```

Then `mdrun`:

```bash
gmx mdrun -deffnm npt0
...
gmx mdrun -deffnm npt22
```

To start umbrella sampling, you will simply have to call `grompp` to process the `.mdp` file for each of the now-equilibrated configurations. Many of the pulling parameters are the same as in the SMD procedure, with the notable exception of `pull_coord1_rate`, which has now been set to zero. We don't want to move the configuration along the reaction coordinate; instead we want to restrain it within a defined window of configurational space. Setting `pull_coord1_start = yes` means that the initial COM distance is the reference distance, and we do not have to define a reference (`pull_coord1_init`) separately for each configuration.

```bash
gmx grompp -f md_umbrella.mdp -c npt0.gro -t npt0.cpt -p topol.top -r npt0.gro -n index.ndx -o umbrella0.tpr
...
gmx grompp -f md_umbrella.mdp -c npt22.gro -t npt22.cpt -p topol.top -r npt22.gro -n index.ndx -o umbrella22.tpr
```

Now, each input file should be passed to `mdrun` for the actual data collection simulation. Once all of the simulations are complete, you can proceed to data analysis.

```bash
gmx mdrun -deffnm umbrella0
...
gmx mdrun -deffnm umbrella22
```

Mike Harms has contributed a Python script that automates this process, extracting coordinate files and setting up the `grompp` and `mdrun` commands to streamline this process.
