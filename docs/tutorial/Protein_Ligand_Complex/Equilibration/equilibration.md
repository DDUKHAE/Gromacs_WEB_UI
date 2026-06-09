# Equilibration

Equilibrating our protein-ligand complex will be much like equilibrating any other system containing a protein in water. There are a few special considerations, in this case:
1.  Applying restraints to the ligand
2.  Treatment of temperature coupling groups

To restrain the ligand, we will need to generate a position restraint topology for it. First, create an index group for JZ4 that contains only its non-hydrogen atoms:

```bash
gmx make_ndx -f jz4.gro -o index_jz4.ndx
```
Type `0 & ! a H*` then `q`.

Then, execute the `genrestr` module and select this newly created index group (which will be group 3 in the `index_jz4.ndx` file):

```bash
gmx genrestr -f jz4.gro -n index_jz4.ndx -o posre_jz4.itp -fc 1000 1000 1000
```

Now, we need to include this information in our topology. We can do this in several ways, depending upon the conditions we wish to use. If we simply want to restrain the ligand whenever the protein is also restrained, add the following lines to your topology in the location indicated:

```gromacs
; Include Position restraint file
#ifdef POSRES
#include "posre.itp"
#endif

; Include ligand topology
#include "jz4.itp"

; Ligand position restraints
#ifdef POSRES
#include "posre_jz4.itp"
#endif

; Include water topology
#include "./charmm36-jul2022.ff/tip3p.itp"
```

Location matters! You must put the call for `posre_jz4.itp` in the topology as indicated. The parameters within `jz4.itp` define a `[ moleculetype ]` directive for our ligand. The moleculetype ends with the inclusion of the water topology (`tip3p.itp`). Placing the call to `posre_jz4.itp` anywhere else will attempt to apply the position restraint parameters to the wrong moleculetype.

## Temperature Coupling

Proper control of temperature coupling is a sensitive issue. Coupling every moleculetype to its own thermostatting group is a bad idea. For instance, if you do the following: `tc-grps = Protein JZ4 SOL CL` your system will probably blow up, since the temperature coupling algorithms are not stable enough to control the fluctuations in kinetic energy that groups with a few atoms (i.e., JZ4 and CL) will produce. Do not couple every single species in your system separately.

The typical approach is to set `tc-grps = Protein Non-Protein` and carry on. Unfortunately, the "Non-Protein" group also encompasses JZ4. Since JZ4 and the protein are physically linked very tightly, it is best to consider them as a single entity. That is, JZ4 is grouped with the protein for the purposes of temperature coupling. In the same way, the few Cl- ions we inserted are considered part of the solvent. To do this, we need a special index group that merges the protein and JZ4. We accomplish this with the `make_ndx` module:

```bash
gmx make_ndx -f em.gro -o index.ndx
```
Merge the "Protein" (1) and "JZ4" (13) groups: `1 | 13` then `q`.

We can now set `tc-grps = Protein_JZ4 Water_and_ions` to achieve our desired "Protein Non-Protein" effect.

## Part 1: NVT Equilibration

Proceed with NVT equilibration using the NVT `.mdp` file:

```bash
gmx grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -n index.ndx -o nvt.tpr
gmx mdrun -deffnm nvt
```

## Part 2: NPT Equilibration

Once the NVT simulation is complete, proceed to NPT with the NPT `.mdp` file:

```bash
gmx grompp -f npt.mdp -c nvt.gro -t nvt.cpt -r nvt.gro -p topol.top -n index.ndx -o npt.tpr
gmx mdrun -deffnm npt
```
