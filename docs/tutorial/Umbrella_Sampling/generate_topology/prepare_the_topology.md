# Prepare the Topology

Generating a molecular topology for an umbrella sampling simulation is just like any other simulation. Obtain the coordinate file of the structure of interest, and generate the topology from `pdb2gmx`. Some systems will require special consideration (i.e., protein-ligand complexes, membrane proteins, etc). For protein-ligand systems, please consult this tutorial, and for membrane proteins, I recommend this one on the topic. The principles of umbrella sampling are easily extendable to these systems, though we will consider only protein molecules in this tutorial.

The system we will consider here is the dissociation of a single peptide from the growing end of an Aβ42 protofibril, and is based on simulations we recently published. The structure file of the wild-type Aβ42 protofibril used in those simulations, acetylated at the N-terminus of each chain, can be found here. The original PDB accession code is `2BEG`.

Run the structure through `pdb2gmx`:

```bash
gmx pdb2gmx -f 2BEG_model1_capped.pdb -ignh -ter -o complex.gro
```

Choose the GROMOS96 53A6 parameter set, SPC water, "None" for the N-termini, and "COO-" for the C-termini for each chain. Modify `topol_Protein_chain_B.itp` to include the following lines (at the end of the file):

```gromacs
#ifdef POSRES_B
#include "posre_Protein_chain_B.itp"
#endif
```

We will be using chain B as an immobile reference later on in the pulling simulations, hence the need to specially position-restrain this chain only, and none of the others.
