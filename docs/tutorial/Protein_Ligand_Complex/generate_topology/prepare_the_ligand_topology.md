# Prepare the Ligand Topology

We must now deal with the ligand. But how does one come up with parameters for some species that the force field does not automatically recognize? Proper treatment of ligands is one of the most challenging tasks in molecular simulation.

In this tutorial, we will be generating the JZ4 topology with the CGenFF server. CGenFF requires a Sybyl `.mol2` file as its input, to collect rudimentary atom type information and bonded connectivity. CHARMM is also an all-atom force field, meaning all H atoms are explicitly represented. To produce a `.mol2` file and add H atoms, use the Avogadro program. Open `jz4.pdb` in Avogadro, and from the "Build" menu, choose "Add Hydrogens." Avogadro will build all of the H atoms onto the JZ4 ligand. Save a `.mol2` file named `jz4.mol2`.

Several corrections must be made to `jz4.mol2` before it can be used.
The first change that needs to be made is in the `MOLECULE` heading. Replace `*****` with `JZ4`.
Next, fix the residue names and numbers such that they are all the same. This `.mol2` file only contains one molecule, therefore there should only be one residue name and number specified.
Lastly, bond orders in the `@<TRIPOS>BOND` section might not be listed in ascending order. You can use the `sort_mol2_bonds.pl` script to fix this:

```bash
perl sort_mol2_bonds.pl jz4.mol2 jz4_fix.mol2
```

Use `jz4_fix.mol2` in the next step.

Visit the CGenFF server, log into your account, and upload `jz4_fix.mol2`. The CGenFF server will return a topology in the form of a CHARMM "stream" file (extension `.str`). Save its contents from your web browser into a file called `jz4.str`. Examine the contents of `jz4.str` and look at the penalties for the charges and the new dihedral parameters. All of them are very low, suggesting that this topology is of very good quality.

The JZ4 topology in CHARMM format is all well and good, but it's not useful if we are trying to run our simulation in GROMACS. Download a suitable version of the `cgenff_charmm2gmx.py` script from its GitHub site. Perform the conversion with:

```bash
python cgenff_charmm2gmx.py JZ4 jz4_fix.mol2 jz4.str charmm36-jul2022.ff
```

This ligand introduces new bonded parameters that are not part of the existing force field, and these parameters are written to a file called `jz4.prm`. The ligand topology is written to `jz4.itp`, which contains the ligand `[ moleculetype ]` definition.

## Build the Complex

From `pdb2gmx`, we have a file called `3HTB_processed.gro` that contains the processed, force field-compliant structure of our protein. We also have `jz4_ini.pdb` from `cgenff_charmm2gmx.py`. Convert this `.pdb` file to `.gro` format with `editconf`:

```bash
gmx editconf -f jz4_ini.pdb -o jz4.gro
```

Copy `3HTB_processed.gro` to a new file to be manipulated, for instance, call it `complex.gro`. Next, simply copy the coordinate section of `jz4.gro` and paste it into `complex.gro`, below the last line of the protein atoms, and before the box vectors. Since we have added 22 more atoms into the `.gro` file, increment the second line of `complex.gro` to reflect this change.

## Build the Topology

Including the parameters for the JZ4 ligand in the system topology is very easy. Just insert a line that says `#include "jz4.itp"` into `topol.top` after the position restraint file is included:

```gromacs
; Include Position restraint file
#ifdef POSRES
#include "posre.itp"
#endif

; Include ligand topology
#include "jz4.itp"

; Include water topology
#include "./charmm36-jul2022.ff/tip3p.itp"
```

The ligand introduces new dihedral parameters, which were written to `jz4.prm`. At the TOP of `topol.top`, insert an `#include` statement to add these parameters:

```gromacs
; Include forcefield parameters
#include "./charmm36-jul2022.ff/forcefield.itp"

; Include ligand parameters
#include "jz4.prm"

[ moleculetype ]
```

The placement of this `#include` statement is critical - it must appear before any `[ moleculetype ]` entry and AFTER the `#include` statement for the parent force field.

The last adjustment to be made is in the `[ molecules ]` directive to add the new molecule:

```gromacs
[ molecules ]
; Compound        #mols
Protein_chain_A     1
JZ4                 1
```

The topology and coordinate file are now in agreement with respect to the contents of the system.
