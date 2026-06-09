# Theory

This tutorial will focus on practical aspects of running free energy calculations in GROMACS. The objective of this tutorial is to reproduce the results of a very simple system for which an accurate free energy estimate exists (methane in water).

Rather than use the thermodynamic integration approach for evaluating free energy differences, the data analysis conducted here will utilize the GROMACS `bar` module. It uses the Bennett Acceptance Ratio (BAR, hence the name of the module) method for calculating free energy differences.

Free energy calculations have a number of practical applications, of which some of the more common ones include free energies of solvation/hydration and free energy of binding for a small molecule to some larger receptor biomolecule. Both of these procedures involve the need to either add (introduce/couple) or remove (decouple/annihilate) the small molecule of interest from the system and calculate the resulting free energy change.

There are two types of nonbonded interactions that can be transformed during free energy calculations, Coulombic and van der Waals interactions. For this tutorial, we will calculate the free energy of a very simple process: turning off the Lennard-Jones interactions between the atomic sites of a molecule of interest (in this case, methane) in water.

# Examine the Topology

Download the coordinate file and topology for this system. The system contains a single molecule of methane (called "ALAB" in the coordinate file) in a box of 596 TIP3P water molecules.

Looking into the topology, we find:

```gromacs
; Topology for methane in TIP3P
#include "oplsaa.ff/forcefield.itp"

[ moleculetype ]
; Name        nrexcl
Methane       3

[ atoms ]
;   nr       type  resnr residue  atom   cgnr     charge       mass  typeB    chargeB      massB
     1   opls_138      1   ALAB     CB      1      0.000     12.011
     2   opls_140      1   ALAB    HB1      2      0.000      1.008
     3   opls_140      1   ALAB    HB2      3      0.000      1.008
     4   opls_140      1   ALAB    HB3      4      0.000      1.008
     5   opls_140      1   ALAB    HB4      5      0.000      1.008

[ bonds ]
;  ai    aj funct       c0       c1       c2       c3
    1     2     1
    1     3     1
    1     4     1
    1     5     1

[ angles ]
;  ai    aj    ak funct       c0       c1       c2       c3
    2     1     3     1
    2     1     4     1
    2     1     5     1
    3     1     4     1
    3     1     5     1
    4     1     5     1

; water topology
#include "oplsaa.ff/tip3p.itp"

[ system ]
; Name
Methane in water

[ molecules ]
; Compound        #mols
Methane           1
SOL               596
```

You will note that all charges are set to zero. There is a practical reason behind this setup. Normally, charge interactions between the solute and water are turned off prior to the van der Waals terms. If charge interactions are left on when Lennard-Jones terms are turned off, positive and negative charges would be allowed to approach one another at infinitely close distances, resulting in a very unstable system. We will be turning off only van der Waals interactions between the solute and solvent.
