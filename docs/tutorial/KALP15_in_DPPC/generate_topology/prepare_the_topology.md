# Prepare the Topology

The protein we will be working with is the KALP model peptide, denoted KALP15, which has a sequence of: `Ac-GKK(LA)4LKKA-NH2`. The protocol described [here](http://dx.doi.org/10.1529/biophysj.105.073395) is based on a system built by Kandasamy and Larson in a study of hydrophobic mismatch. The original reference can be found here.

The peptide was prepared in-house using the xLeap module of [AmberTools](http://ambermd.org/#AmberTools), using ideal backbone geometry of an α-helix (φ = -60°, ψ = -40°). The `.pdb` file was oriented along the z-axis using `editconf -princ`, followed by a rotation about the y axis. Note that in GROMACS-3.3.x, the `-princ` option oriented the long axis of the structure (in this case, the helix axis) along the z-axis by default, but this option has changed as of GROMACS-4.0.4, which orients the long axis along the x-axis. If you want to skip the construction of this peptide, the properly oriented structure can be found [here](http://www.mdtutorials.com/gmx/2018/membrane_protein/Files/KALP-15_princ.pdb).

Execute `pdb2gmx` by issuing the following command:

```bash
gmx pdb2gmx -f KALP-15_princ.pdb -o KALP-15_processed.gro -ignh -ter -water spc
```

When prompted, choose the **GROMOS96 53A6** parameter set. Choose "None" for the termini; since we have added acetyl and amide capping groups to the N- and C-termini, respectively, we do not want `pdb2gmx` to build the normal amine and carboxyl groups. Instead, we want `pdb2gmx` to add connectivity to our capping groups. 

The `-ignh` flag tells `pdb2gmx` to ignore the H atoms in the input. By default, xLeap gave us an all-atom structure (since the AMBER force fields use explicit hydrogen representation). Due to AMBER naming conventions, these H atoms may not have the same nomenclature as those of the GROMOS96 force field. If we tell `pdb2gmx` to ignore all input H atoms, it will add back only those that it needs.

Now we will need to make some alterations to the topology.
