# Prepare the Protein Topology

We must download the protein structure file we will be working with. For this tutorial, we will utilize T4 lysozyme L99A/M102Q (PDB code 3HTB). Go to the RCSB website and download the PDB text for the crystal structure.

Once you have downloaded the structure, you can visualize it using a viewing program such as VMD, Chimera, PyMOL, etc. Once you've had a look at the molecule, you are going to want to strip out the crystal waters, PO4, and BME. Note that such a procedure is not universally appropriate (i.e., the case of a bound active site water molecule). For our intentions here, we do not need crystal water or other species, which are just crystallization co-solvents. We will instead focus on the ligand called "JZ4," which is 2-propylphenol.

If you want a clean version of the `.pdb` file to check your work, you can download it here. The problem we now face is that the JZ4 ligand is not a recognized entity in any of the force fields provided with GROMACS, so `pdb2gmx` will give a fatal error if you were try to pass this file through it. Topologies can only be assembled automatically if an entry for a building block is present in the `.rtp` (residue topology) file for the force field. Since this is not the case, we will prepare our system topology in two steps:

1.  Prepare the protein topology with `pdb2gmx`
2.  Prepare the ligand topology using external tools

Since we will be preparing these two topologies separately, we must save the protein and JZ4 ligand into separate coordinate files. Save the JZ4 coordinates like so:

```bash
grep JZ4 3HTB_clean.pdb > jz4.pdb
```

Then simply delete the JZ4 lines from `3HTB_clean.pdb`. At this point, preparing the protein topology is trivial. The force field we will be using in this tutorial is CHARMM36, obtained from the MacKerell lab website. While there, download the latest CHARMM36 force field tarball and the `cgenff_charmm2gmx.py` conversion script, which we will use later.

Unarchive the force field tarball in your working directory:

```bash
tar -zxvf charmm36-jul2022.ff.tgz
```

There should now be a `charmm36-jul2022.ff` subdirectory in your working directory. Write the topology for the T4 lysozyme with `pdb2gmx`:

```bash
gmx pdb2gmx -f 3HTB_clean.pdb -o 3HTB_processed.gro -ter
```

You will be prompted to make 3 selections:
1.  **Force field**: Choose the CHARMM36 force field.
2.  **Water model**: Choose the default water model (CHARMM-modified TIP3P).
3.  **Terminus type**: Choose "NH3+" and "COO-" for the termini. This interactive selection is necessary due to the N-terminal residue being methionine (MET), which causes `pdb2gmx` to choose an incompatible terminus type. You must select the protein-specific termini, otherwise you will get a fatal error about non-matching atom names.
