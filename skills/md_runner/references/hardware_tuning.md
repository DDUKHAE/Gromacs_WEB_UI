# Hardware Tuning

`state.hardware.ntomp` is computed as `cpu_count / max(1, n_gpus)` at
workspace init. `mdrun` is invoked with `-ntomp` to spread OpenMP
threads across the available GPUs. To pin to specific GPUs, set
`GMX_GPU_ID` in the environment before invoking md-runner.

If `nvidia-smi` is unavailable, GPU detection returns an empty list and
md-runner runs CPU-only. The user can override via
`phase_overrides.global = {"gpu_id": "0,1"}` (handled by future
extension; currently ignored).
