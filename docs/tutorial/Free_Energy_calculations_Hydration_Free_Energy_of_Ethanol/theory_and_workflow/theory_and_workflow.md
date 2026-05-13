# Theory

This tutorial focuses on calculating the hydration free energy (ΔG_hydr) of ethanol, a value that is well characterized experimentally. The value of ΔG_hydr is useful for determining how well a force field models interactions between a solute and an aqueous environment, therefore this quantity is often used as validation when developing new parameters.

Physically, ΔG_hydr corresponds to the transfer of a molecule of the solute in the (ideal) gas phase into an infinitely dilute aqueous solution. This tutorial will apply a λ-dependent transformation and use the Bennett Acceptance Ratio (BAR).

# The Workflow

We will begin by generating a topology for ethanol and solvating it in a box of water. For this tutorial, we will be using the CHARMM force field, specifically the CHARMM General Force Field to represent ethanol.

Generate the topology for ethanol and center it in a cubic box of water with the following commands:

```bash
gmx pdb2gmx -f etoh.pdb -o etoh.gro
gmx editconf -f etoh.gro -o etoh_box.gro -c -box 4.0
gmx solvate -cp etoh_box.gro -cs spc216.gro -o etoh_solv.gro -p topol.top
```

The free energy change of transforming a system from state A to state B, ΔG_AB, is a function of a coupling parameter, λ, which indicates the level of change that has taken place between states A (λ = 0) and B (λ = 1).

Simulations conducted at different values of λ allow us to plot a ∂H/∂λ curve, from which ΔG_AB is obtained. The first step in planning free energy calculations is determining how many λ points will be used to describe the transformation from state A (λ = 0) to state B (λ = 1).

For each value of λ, a complete workflow (energy minimization, equilibration, and data collection) must be conducted. The workflow utilized here will be:
1.  Steepest descents minimization
2.  NVT equilibration
3.  NPT equilibration
4.  Data collection under an NPT ensemble

Given that we are transforming both Coulombic and van der Waals terms here, we will take a moment to look at the λ vectors a bit more closely:

```gromacs
init_lambda_state        = 0
; init_lambda_state        0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16   17   18   19   20   21   22   23   24   25   27   28   29   30
vdw_lambdas              = 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.05 0.10 0.15 0.20 0.25 0.30 0.35 0.40 0.45 0.50 0.55 0.60 0.65 0.70 0.75 0.80 0.85 0.90 0.95 1.00
coul_lambdas             = 0.00 0.10 0.20 0.30 0.40 0.50 0.60 0.70 0.80 0.90 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00
```

Setting `initial_lambda_state = 1` would correspond to the next column to the right (λ for electrostatics = 0.10), while `initial_lambda_state = 30` would specify the final column (λ vector), in which the value of λ for van der Waals and electrostatics = 1.0.

The conventional approach when transforming both electrostatic and van der Waals terms is to remove the charges first, followed by van der Waals terms. If done in the opposite order, atoms would not repel from one another and charges would collapse into themselves, resulting in Coulombic singularities and the simulations will crash. Conversely, if one is transforming from a non-interacting state, the van der Waals terms should be switched on first, followed by electrostatic terms.
