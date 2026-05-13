# Defining the Unit Cell & Adding Solvent

Defining a unit cell for a membrane protein is considerably more complicated than for a protein in water. There are several key steps in building the unit cell:

1. Orient the protein and membrane in the same coordinate frame
2. Pack the lipids around the protein
3. Solvate with water

## 1. Orient the protein and membrane

We have already aligned the KALP peptide using `editconf`. The bilayer lies in the x-y plane, with the normal along the z-axis. To remove the effects of periodicity, use `trjconv`:

(1) Generate a `.tpr` file for a DPPC-only system using `grompp`. Run `grompp` with `dppc128.pdb` and `topol_dppc.top`:

```bash
gmx grompp -f minim.mdp -c dppc128.pdb -p topol_dppc.top -o dppc.tpr -maxwarn 1
```

(2) Use `trjconv` to remove periodicity (select group 0, "System" for output):

```bash
gmx trjconv -s dppc.tpr -f dppc128.pdb -o dppc128_whole.gro -pbc mol -ur compact
```

Now, take a look at the last line of this `.gro` file; it corresponds to the x/y/z box vectors of the DPPC unit cell. We need to orient the KALP peptide within this same coordinate frame, and place the center of mass of the peptide at the center of this box:

```bash
gmx editconf -f KALP-15_processed.gro -o KALP_newbox.gro -c -box 6.41840 6.44350 6.59650
```

The center of our system now lies at (3.20920, 3.22175, 3.29825), half of each box vector.

## 2. Pack the lipids around the protein

The easiest method for packing lipids around an embedded protein is the InflateGRO methodology. First, concatenate the protein and bilayer structure files:

```bash
cat KALP_newbox.gro dppc128_whole.gro > system.gro
```

Remove unnecessary lines (the box vectors from the KALP structure, the header information from the DPPC structure) and update the second line of the coordinate file (total number of atoms) accordingly.

Add a new `#ifdef` statement to your topology to call strong position restraints:

```gromacs
; Include Position restraint file
#ifdef POSRES
#include "posre.itp"
#endif

; Strong position restraints for InflateGRO
#ifdef STRONG_POSRES
#include "strong_posre.itp"
#endif

; Include DPPC chain topology
#include "dppc.itp"

; Include water topology
#include "gromos53a6_lipid.ff/spc.itp"
```

Generate this new position restraint file using `genrestr`:

```bash
gmx genrestr -f KALP_newbox.gro -o strong_posre.itp -fc 100000 100000 100000
```

In the `.mdp` file used for the minimizations, add a line `define = -DSTRONG_POSRES`. Then run InflateGRO to scale lipid positions by a factor of 4:

```bash
perl inflategro.pl system.gro 4 DPPC 14 system_inflated.gro 5 area.dat
```

Note how many lipids were deleted and update the `[ molecules ]` directive of your topology accordingly. Run energy minimization:

```bash
gmx grompp -f minim_inflategro.mdp -c system_inflated.gro -p topol.top -r system_inflated.gro -o system_inflated_em.tpr
gmx mdrun -deffnm system_inflated_em
```

Reconstruct with `trjconv` before using such coordinates with InflateGRO:

```bash
gmx trjconv -s system_inflated_em.tpr -f system_inflated_em.gro -o tmp.gro -pbc mol
mv tmp.gro system_inflated_em.gro
```

Begin packing the lipids by shrinking by a factor of 0.95:

```bash
perl inflategro.pl system_inflated_em.gro 0.95 DPPC 0 system_shrink1.gro 5 area_shrink1.dat
```

Follow this up by another round of EM. Repeat shrinking and EM iterations until the area per lipid reaches an appropriate value.

## 3. Solvate with water

Solvating a membrane protein system has a tendency to fill gaps in the lipid acyl chains with water molecules. Proceed with solvation:

```bash
gmx solvate -cp system_shrink26_em.gro -cs spc216.gro -o system_solv.gro -p topol.top
```

Use `water_deletor.pl` to delete these interior water molecules:

```bash
perl water_deletor.pl -in system_solv.gro -out system_solv_fix.gro -ref O33 -middle C50 -nwater 3
```

The script tells you how many water molecules it deleted and how many remain. Update the `SOL` line in `topol.top` with this updated number of water molecules.
