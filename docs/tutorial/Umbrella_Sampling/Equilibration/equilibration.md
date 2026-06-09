# Energy Minimization and Equilibration

The energy minimization and equilibration steps are going to be conducted just like any other protein-in-water system. Here, we will perform steepest descents minimization followed by NPT equilibration.

Invoke `grompp` and `mdrun`, as usual:

```bash
gmx grompp -f minim.mdp -c solv_ions.gro -p topol.top -o em.tpr
gmx mdrun -v -deffnm em

gmx grompp -f npt.mdp -c em.gro -p topol.top -r em.gro -o npt.tpr
gmx mdrun -deffnm npt
```
