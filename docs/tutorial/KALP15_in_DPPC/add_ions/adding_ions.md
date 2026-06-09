# Adding Ions

Now that we have solvated our system and removed water molecules from the hydrophobic core of the membrane, it is time to add neutralizing counterions. At this point, the process for continuing with building our system is nearly identical to that of the lysozyme tutorial.

```bash
gmx grompp -f ions.mdp -c system_solv_fix.gro -p topol.top -o ions.tpr
```

Since the KALP15 peptide contains 4 lysine residues, the peptide bears a net charge of +4e at neutral pH. Use `genion` to add 4 Cl- ions to neutralize this charge:

```bash
gmx genion -s ions.tpr -o system_solv_ions.gro -p topol.top -pname NA -nname CL -neutral
```
