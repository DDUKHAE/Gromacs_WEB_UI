# Production MD

Upon completion of the two equilibration phases, the system is now well-equilibrated at the desired temperature and pressure. We are now ready to release the position restraints and run production MD for data collection. The process is much like we have seen before. We will run a 1-ns MD simulation.

```bash
gmx grompp -f md.mdp -c npt.gro -t npt.cpt -p topol.top -n index.ndx -o md_0_1.tpr
```

Again, execute `mdrun`:

```bash
gmx mdrun -deffnm md_0_1
```

To continue your simulation beyond 1 ns, making use of the checkpointing feature of GROMACS, refer to the [GROMACS website](http://www.gromacs.org/Documentation/How-tos/Extending_Simulations).
