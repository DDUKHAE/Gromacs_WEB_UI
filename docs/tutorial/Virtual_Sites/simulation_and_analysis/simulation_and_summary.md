# Simple Simulations

We will now generate a simple system to simulate. Create a simple box of CO2 molecules using `insert-molecules`:

```bash
gmx insert-molecules -ci co2.pdb -nmol 10 -box 10 10 10 -o box.pdb
```

We do this because if we attempt to simulate only a single molecule, there are no degrees of freedom and the simulation is effectively conducted at 0 K, so nothing moves. That's not very useful or effective at demonstrating that this model works, so we work with a small test system. Now, update the `[ molecules ]` section of `topol.top` to reflect the fact that there are now 10 total CO2 molecules in the system.

```gromacs
[ molecules ]
; Compound        #mols
CO2               10
```

Run energy minimization using the appropriate `.mdp` file.

```bash
gmx grompp -f em.mdp -c box.pdb -p topol.top -o em.tpr
gmx mdrun -nt 1 -nb cpu -deffnm em
```

The system is very small (50 particles) and thus it does not make sense to try to parallelize the simulation, so only one thread is used (`-nt 1`).

Now run a short simulation on the system using the production `.mdp` file.

```bash
gmx grompp -f md.mdp -c em.gro -p topol.top -o md.tpr
gmx mdrun -nt 1 -nb cpu -deffnm md
```

The CO2 molecules float around in space, which is expected but not particularly important. What is important to note is that the geometry of the molecules is constructed correctly in each frame.

# Analysis

Additionally, we can verify that the moment of inertia of each molecule was correct using the `principal` module. For ease of understanding, we can analyze each molecule separately:

```bash
gmx make_ndx -f em.gro
```
Type: `splitres 0` then `q`.

```bash
gmx principal -s md.tpr -f md.trr -n index.ndx
# choose any molecule for analysis when prompted
```

The output in `moi.dat` contains the moment of inertia along the x-, y-, and z-axes. The moment of inertia along the x-axis of CO2 (along the C=O bonds) is zero, while the values of the moments of inertia along the y- and z-axes are approximately 0.500, which is in perfect agreement with the value calculated before when setting up the topology. Therefore, we conclude that this model of CO2 adequately reproduces the expected moment of inertia.

# Summary

You have now succeeded in creating a custom topology for a linear molecule using virtual sites and used a simple simulation to confirm that the moment of inertia was reproduced correctly. This tutorial can serve as a basis for creating topologies for other linear molecules or functional groups.
