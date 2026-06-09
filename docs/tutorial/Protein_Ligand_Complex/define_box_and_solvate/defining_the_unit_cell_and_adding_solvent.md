# Defining the Unit Cell & Adding Solvent

At this point, the workflow is just like any other MD simulation. We will define the unit cell and fill it with water.

```bash
gmx editconf -f complex.gro -o newbox.gro -bt dodecahedron -d 1.0
gmx solvate -cp newbox.gro -cs spc216.gro -p topol.top -o solv.gro
```

Upon visualizing `solv.gro`, you may wonder why `editconf` did not produce the requested dodecahedral unit cell shape. GROMACS programs always use the most numerically efficient representation of the coordinates, one that has everything re-wrapped into a triclinic unit cell. The desired unit cell shape can be recovered later, following the generation of a `.tpr` file.
