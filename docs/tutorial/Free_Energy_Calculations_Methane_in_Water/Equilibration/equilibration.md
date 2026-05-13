# Equilibration

The system will be equilibrated in two phases, the first at constant volume (NVT), the second at constant pressure (NPT).

```bash
#####################
# NVT EQUILIBRATION #
#####################
echo "Starting constant volume equilibration..."

cd ../
mkdir NVT
cd NVT

gmx grompp -f $MDP/nvt_$LAMBDA.mdp -c ../EM/min$LAMBDA.gro -p $FREE_ENERGY/topol.top -o nvt$LAMBDA.tpr
gmx mdrun -deffnm nvt$LAMBDA

echo "Constant volume equilibration complete."

#####################
# NPT EQUILIBRATION #
#####################
echo "Starting constant pressure equilibration..."

cd ../
mkdir NPT
cd NPT

gmx grompp -f $MDP/npt_$LAMBDA.mdp -c ../NVT/nvt$LAMBDA.gro -p $FREE_ENERGY/topol.top -t ../NVT/nvt$LAMBDA.cpt -o npt$LAMBDA.tpr
gmx mdrun -deffnm npt$LAMBDA

echo "Constant pressure equilibration complete."
```
