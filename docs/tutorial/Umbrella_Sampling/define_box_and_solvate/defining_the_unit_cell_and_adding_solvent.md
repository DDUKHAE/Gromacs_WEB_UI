# Defining the Unit Cell and Adding Solvent & Ions

## Step 1: Define the Unit Cell

Defining the unit cell for a pulling simulation is not unlike defining the unit cell for any other simulation. There is, however, one major consideration. One must allow enough space in the pulling direction to allow for a continuous pull without interacting with the periodic images of the system. That is, the minimum image convention must be continually satisfied, and as well, the pull distance must always be less than one-half the length of the box vector along which the pulling is being conducted.

GROMACS calculates distances while simultaneously taking periodicity into account. Thus, if you have a 10-nm box, and you pull over a distance greater than 5.0 nm, the periodic distance becomes the reference distance for the pulling, and this distance is actually less than 5.0 nm! This fact will significantly affect results, since the distance you think you are pulling is not what is actually calculated.

We will be pulling a total distance of 5.0 nm in a 12.0-nm box, to avoid the complications described above. The center of mass of the protofibril will be placed at (3.280, 2.181, 2.4775) in a box of dimensions 6.560 x 4.362 x 12. Use `editconf` to place the protofibril at this location:

```bash
gmx editconf -f complex.gro -o newbox.gro -center 3.280 2.181 2.4775 -box 6.560 4.362 12
```

You can visualize the location of the protofibril within the box using, for example, VMD. Load the structure in VMD and open the Tk console. Type the following:

```tcl
> pbc box
```

## Step 2: Adding Solvent and Ions

First, we will add water with `solvate`:

```bash
gmx solvate -cp newbox.gro -cs spc216.gro -o solv.gro -p topol.top
```

Next, we will add ions using `genion`. We are going to be conducting these simulations in the presence of 100 mM NaCl, on top of neutralizing counterions:

```bash
gmx grompp -f ions.mdp -c solv.gro -p topol.top -o ions.tpr
gmx genion -s ions.tpr -o solv_ions.gro -p topol.top -pname NA -nname CL -neutral -conc 0.1
```

Select group 13 (SOL) to replace water molecules with ions.
