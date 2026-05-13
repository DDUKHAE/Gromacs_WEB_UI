# Equilibration

EM ensured that we have a reasonable starting structure, in terms of geometry and solvent orientation. To begin real dynamics, we must equilibrate the solvent and ions around the protein. If we were to attempt unrestrained dynamics at this point, the system may collapse. The reason is that the solvent is mostly optimized within itself, and not necessarily with the solute. It needs to be brought to the temperature we wish to simulate and establish the proper orientation about the solute (the protein). After we arrive at the correct temperature (based on kinetic energies), we will apply pressure to the system until it reaches the proper density.

Remember that `posre.itp` file that `pdb2gmx` generated a long time ago? We're going to use it now. The purpose of `posre.itp` is to apply a position restraining force on the heavy atoms of the protein (anything that is not a hydrogen). Movement is permitted, but only after overcoming a substantial energy penalty. The utility of position restraints is that they allow us to equilibrate our solvent around our protein, without the added variable of structural changes in the protein. The origin of the position restraints (the coordinates at which the restraint potential is zero) is provided via a coordinate file passed to the `-r` option of `grompp`.

## Part 1: NVT Equilibration

Equilibration is often conducted in two phases. The first phase is conducted under an NVT ensemble (constant Number of particles, Volume, and Temperature). This ensemble is also referred to as "isothermal-isochoric" or "canonical." The timeframe for such a procedure is dependent upon the contents of the system, but in NVT, the temperature of the system should reach a plateau at the desired value. If the temperature has not yet stabilized, additional time will be required. Typically, 50-100 ps should suffice, and we will conduct a 100-ps NVT equilibration for this exercise. Depending on your machine, this may take a while (just under an hour if run in parallel on 16 cores or so). Using a modest, consumer-grade GPU to accelerate the calculation will allow you to complete this simulation in 1-2 minutes. Get the `.mdp` file here.

We will call `grompp` and `mdrun` just as we did at the EM step:

```bash
gmx grompp -f inputs/nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr

gmx mdrun -deffnm nvt
```

A full explanation of the parameters used can be found in the GROMACS manual, in addition to the comments provided. Take note of a few parameters in the `.mdp` file:

*   `gen_vel = yes`: Initiates velocity generation. Using different random seeds (`gen_seed`) gives different initial velocities, and thus multiple (different) simulations can be conducted from the same starting structure.
*   `tcoupl = V-rescale`: The stochastic velocity rescaling thermostat of Bussi et al.
*   `pcoupl = no`: Pressure coupling is not applied.

Let's analyze the temperature progression, again using `energy`:

```bash
gmx energy -f nvt.edr -o temperature.xvg
```

Type "16 0" at the prompt to select the temperature of the system and exit. The resulting plot should look something like the following:

![NVT Temperature](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_nvt_temperature.png)

From the plot, it is clear that the temperature of the system quickly reaches the target value (298 K), and remains stable over the remainder of the equilibration. For this system, a shorter equilibration period (on the order of 50 ps) may have been adequate.

## Part 2: NPT Equilibration

The previous step, NVT equilibration, stabilized the temperature of the system. Prior to data collection, we must also stabilize the pressure (and thus also the density) of the system. Equilibration of pressure is conducted under an NPT ensemble, wherein the Number of particles, Pressure, and Temperature are all constant. The ensemble is also called the "isothermal-isobaric" ensemble, and most closely resembles experimental conditions.

The `.mdp` file used for a 500-ps NPT equilibration can be found here. It is not drastically different from the parameter file used for NVT equilibration, though this phase of equilibration usually takes somewhat longer than NVT equilibration because pressure takes a little longer to relax than temperature. Note the addition of the pressure coupling section, using the C-rescale barostat.

A few other changes:

*   `continuation = yes`: We are continuing the simulation from the NVT equilibration phase
*   `gen_vel = no`: Velocities are read from the trajectory (see below)

We will call `grompp` and `mdrun` just as we did for NVT equilibration. Note that we are now including the `-t` flag to include the checkpoint file from the NVT equilibration; this file contains all the necessary state variables to continue our simulation. To conserve the velocities produced during NVT, we must include this file. The coordinate file (`-c`) is the final output of the NVT simulation.

```bash
gmx grompp -f inputs/npt.mdp -c nvt.gro -r nvt.gro -t nvt.cpt -p topol.top -o npt.tpr

gmx mdrun -deffnm npt
```

Let's analyze the pressure progression, again using `energy`:

```bash
gmx energy -f npt.edr -o pressure.xvg
```

Type "17 0" at the prompt to select the pressure of the system and exit. The resulting plot should look something like the following:

![NPT Pressure](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_npt_pressure.png)

The pressure value fluctuates widely over the course of the 100-ps equilibration phase, but this behavior is not unexpected. The running average of these data are plotted as the red line in the plot. Over the course of the equilibration, the average value of the pressure is -3 ± 11 bar. Note that the reference pressure was set to 1 bar, so is this outcome acceptable? Pressure is a quantity that fluctuates widely over the course of an MD simulation, as is clear from the error bar (11 bar), so statistically speaking, one cannot distinguish a difference between the obtained average (-3 ± 11 bar) and the target/reference value (1 bar).

Let's take a look at density as well, this time using `energy` and entering "23 0" at the prompt.

```bash
gmx energy -f npt.edr -o density.xvg
```

![NPT Density](http://www.mdtutorials.com/gmx/lysozyme/Images/plot_lyso_npt_density.png)

As with the pressure, the running average of the density is also plotted in red. The average value over the course of 500 ps is 1025.3 ± 0.5 kg m-3, higher than the experimental value of 1000 kg m-3 and the expected density of the TIP3P model of 986 kg m-3. Is this result reasonable? We have not simulated pure water; instead, there is a protein in our system and some diffuse ions. Therefore, we should not expect an exact match, and during equilibration, we need only to see that the density has stabilized.

Please note: I frequently get questions about why density values obtained do not match my results. Pressure-related terms are slow to converge, and there are elements of randomness in any MD simulation. You will almost certainly not reproduce this outcome exactly.
