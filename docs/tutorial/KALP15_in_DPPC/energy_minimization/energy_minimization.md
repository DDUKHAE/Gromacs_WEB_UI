# Energy Minimization

Assemble the binary input using `grompp` using the input parameter file:

```bash
gmx grompp -f minim.mdp -c system_solv_ions.gro -p topol.top -o em.tpr
```

Invoke `mdrun`:

```bash
gmx mdrun -v -deffnm em
```

As with any other simulation, verify that the values of Epot and Fmax are reasonable before continuing. Membrane protein systems can be tricky, because there are a number of potential problems. If your system is not converging, consider the following factors:

1.  **Intra-headgroup hydrogen bonding**, like in PE or PG headgroups. Sometimes simulations collapse because the headgroups fold in on themselves within voids in the solvent.
    *   Use position restraints or freeze groups during equilibration until the solvent is optimized around the lipid headgroups.
    *   Reduce the charges on the H atoms (all the way to zero, if necessary). Restore the charges before continuing!
    *   Add `[ exclusions ]` within the topology between H and phosphate O atoms. Remove the exclusions before continuing!
2.  **Acyl chain overlap** can occur during packing. Run InflateGRO carefully, and do not attempt to over-pack your lipids.
3.  **Protein-lipid overlap.** Did you choose an appropriate cut-off value in the initial InflateGRO step?
4.  **Water-headgroup and ion-headgroup overlap.** Sometimes `solvate` and `genion` are not smart, especially regarding random placement of ions. A Cl- next to a phosphate can send the ion (or lipid) careening across the simulation box!

Now that our system is at an energy minimum, we can begin real dynamics.
