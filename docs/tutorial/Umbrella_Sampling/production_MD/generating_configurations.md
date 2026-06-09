# Generating Configurations

To conduct umbrella sampling, one must generate a series of configurations along a reaction coordinate, ζ. Some of these configurations will serve as the starting configurations for the umbrella sampling windows, which are run in independent simulations. 

For this example, the reaction coordinate is the z-axis. To generate these configurations, we must pull peptide A away from the protofibril. We will pull over the course of 500 ps of MD, saving snapshots every 1 ps. This setup has been established based on trial-and-error to obtain a reasonable distribution of configurations.

A brief explanation of the pulling options used in the `.mdp` file:

```gromacs
; Pull code
pull = yes
pull_ncoords = 1         ; only one reaction coordinate
pull_ngroups = 2         ; two groups defining one reaction coordinate
pull_group1_name = Chain_A
pull_group2_name = Chain_B
pull_coord1_type = umbrella  ; harmonic potential
pull_coord1_geometry = distance  ; simple distance increase
pull_coord1_dim = N N Y      ; pull along z
pull_coord1_groups = 1 2     ; groups 1 (Chain A) and 2 (Chain B) define the reaction coordinate
pull_coord1_start = yes      ; define initial COM distance > 0
pull_coord1_rate = 0.01      ; 0.01 nm per ps = 10 nm per ns
pull_coord1_k = 1000         ; kJ mol^-1 nm^-2
```

*   **`pull = yes`**: tells grompp to read settings for COM pulling.
*   **`pull_ncoords = 1`**: defines the number of reaction coordinates that are present in the system.
*   **`pull_ngroups = 2`**: there are two groups that define the ends of the reaction coordinate.
*   **`pull_coord1_type = umbrella`**: using a harmonic potential to pull. IMPORTANT: This procedure is NOT umbrella sampling. The harmonic potential allows the force to vary according to the nature of the interactions.
*   **`pull_coord1_geometry = distance`**: defines the geometry.
*   **`pull_coord1_dim = N N Y`**: we are applying a bias only in the z-dimension.
*   **`pull_coord1_start = yes`**: the initial COM distance is the reference distance for the first frame.
*   **`pull_coord1_rate = 0.01`**: the rate at which the imaginary spring attached to our pull groups is elongated. This type of pulling is also called "constant velocity".
*   **`pull_coord1_k = 1000`**: the force constant on the spring used for pulling.

We will need to define some custom index groups for this pulling simulation. Use `make_ndx`:

```bash
gmx make_ndx -f npt.gro
```
Type: `r 1-27` -> `name 19 Chain_A` -> `r 28-54` -> `name 20 Chain_B` -> `q`.

Now, run the steered MD simulation:

```bash
gmx grompp -f md_pull.mdp -c npt.gro -p topol.top -r npt.gro -n index.ndx -t npt.cpt -o pull.tpr
gmx mdrun -deffnm pull -pf pullf.xvg -px pullx.xvg
```

To prepare the individual umbrella sampling windows, we will need to extract useful frames from the SMD trajectory. The easiest way is the following:
1. Define the spacing of the windows (generally 0.1 - 0.2 nm)
2. Extract all the frames from the pulling trajectory that was just produced
3. Measure the COM distance of each of these frames between the two groups defining the reaction coordinate 
4. Use the selected frames for umbrella sampling input

To extract the frames from your trajectory (`pull.xtc`), use `trjconv` (save the whole system, group 0, when prompted):

```bash
gmx trjconv -s pull.tpr -f pull.xtc -o conf.gro -sep
```

A series of coordinate files (`conf0.gro`, `conf1.gro`, etc) will be produced, corresponding to each of the frames saved in the continuous pulling simulation. You can use `gmx distance` to measure the distance and select windows. You would then use `confX.gro` as the starting configurations of umbrella sampling windows based on the desired spacing (e.g. 0.2-nm spacing).
