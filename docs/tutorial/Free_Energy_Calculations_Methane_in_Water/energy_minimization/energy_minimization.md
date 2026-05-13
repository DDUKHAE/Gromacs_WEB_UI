# Energy Minimization

The `job.sh` script I provide for running these calculations will create the following directory hierarchy:

```text
Lambda_0/
    Lambda_0/EM/
    Lambda_0/NVT/
    Lambda_0/NPT/
    Lambda_0/Production_MD/
```

This way, all steps in the workflow are executed within a single directory for each value of `init_lambda_state`.

As described before, energy minimization will be conducted using the steepest descent method. The relevant section in the `job.sh` script is:

```bash
mkdir Lambda_$LAMBDA
cd Lambda_$LAMBDA

#################################
# ENERGY MINIMIZATION 1: STEEP  #
#################################
echo "Starting minimization for lambda = $LAMBDA..."

mkdir EM
cd EM

# Iterative calls to grompp and mdrun to run the simulations
gmx grompp -f $MDP/em_steep_$LAMBDA.mdp -c $FREE_ENERGY/methane_water.gro -p $FREE_ENERGY/topol.top -o min$LAMBDA.tpr
gmx mdrun -deffnm min$LAMBDA

echo "Minimization complete."
```
