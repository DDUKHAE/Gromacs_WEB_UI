# Adding Ions

We now have a solvated system that contains a charged protein. The output of `pdb2gmx` told us that the protein has a net charge of +6e (based on its amino acid composition). If you missed this information in the `pdb2gmx` output, look at the last line of your `[ atoms ]` directive in `topol.top`; it should read (in part) "qtot 6." Since life does not exist at a net charge, we must add ions to our system.

Use `grompp` to assemble a `.tpr` file, using any `.mdp` file. I use an `.mdp` file for running energy minimization:

```bash
gmx grompp -f ions.mdp -c solv.gro -p topol.top -o ions.tpr
```

We now pass our `.tpr` file to `genion`:

```bash
gmx genion -s ions.tpr -o solv_ions.gro -p topol.top -pname NA -nname CL -neutral
```

The specified atom names are always the elemental symbol in all capital letters, along with the `[ moleculetype ]`. Residue names may or may not append the sign of the charge (+/-). Refer to `ions.itp` for proper nomenclature if you encounter difficulties.

Your `[ molecules ]` directive should now look like:

```gromacs
[ molecules ]
; Compound        #mols
Protein_chain_A     1
JZ4                 1
SOL             10228
CL                  6
```
