# Energy Minimization

Now that the system is assembled, create the binary input using `grompp` using the input parameter file:

```bash
gmx grompp -f em.mdp -c solv_ions.gro -p topol.top -o em.tpr
```

Make sure you have been updating your `topol.top` file when running `genbox` (or `solvate`) and `genion`, or else you will get lots of nasty error messages ("number of coordinates in coordinate file does not match topology," etc).

We are now ready to invoke `mdrun` to carry out the EM:

```bash
gmx mdrun -v -deffnm em
```

As in the lysozyme tutorial, it is possible to monitor various components of the potential energy using the `energy` module. Now that our system is at an energy minimum, we can begin real dynamics.
