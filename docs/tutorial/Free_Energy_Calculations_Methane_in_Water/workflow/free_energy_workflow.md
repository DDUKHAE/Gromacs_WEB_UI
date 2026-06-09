# The Workflow

The free energy change of transforming a system from state A to state B, ΔG_AB, is a function of a coupling parameter, λ, which indicates the level of change that has taken place between states A and B. Simulations conducted at different values of λ allow us to plot a ∂H/∂λ curve, from which ΔG_AB is derived. The first step is planning how many λ points will be used to describe the transformation from state A (λ = 0) to state B (λ = 1).

For decoupling Coulombic interactions, which depend linearly upon λ, an equidistant λ spacing from 0 to 1 should usually suffice, with λ spacing values of 0.05-0.1 being common. For decoupling van der Waals interactions, λ spacing can be much trickier. A great deal of λ points may be necessary to properly describe the transformation. Clustering λ points in regions where the slope of the ∂H/∂λ curve is steep may be necessary. For the purposes of this tutorial, we will use equidistant λ spacing of 0.05.

For each value of λ, a complete workflow (energy minimization, equilibration, and data collection) must be conducted. I generally find it most efficient to run these jobs as batches, passing the output of one step directly into the next. The workflow utilized here will be:

1.  Steepest descents minimization
2.  NVT equilibration
3.  NPT equilibration
4.  Data collection under an NPT ensemble

There are also several differences in the `.mdp` settings that will be used here relative to typical simulations:

1.  `rlist=rcoulomb=rvdw=1.2`. In order to use PME, `rlist` must be equal to `rcoulomb`. The Verlet cutoff scheme requires `rvdw=rcoulomb`.
2.  Temperature coupling is handled through the use of the Langevin integrator (the "sd" setting specifies "stochastic dynamics"), rather than an Andersen thermostat.
3.  `tau_t = 1.0`. When using the Langevin integrator, this value corresponds to an inverse friction coefficient (ps^-1).

Let us take a moment to dissect the λ vectors a bit more closely. For example, `init_lambda_state = 0` means we are specifying the state with index 0 in the `*_lambdas` keywords:

```gromacs
; init_lambda_state        0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16   17   18   19   20
vdw_lambdas              = 0.00 0.05 0.10 0.15 0.20 0.25 0.30 0.35 0.40 0.45 0.50 0.55 0.60 0.65 0.70 0.75 0.80 0.85 0.90 0.95 1.00
coul_lambdas             = 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
```

Setting `initial_lambda_state = 1` would correspond to the next column to the right (λ for van der Waals = 0.05). For the purposes of this tutorial, we are only transforming van der Waals interactions, leaving everything related to charges alone.
