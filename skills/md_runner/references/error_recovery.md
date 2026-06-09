# Error Recovery Rules

| Cause | First mutation | Second | Third |
|---|---|---|---|
| unstable_energy | `{nsteps: 100}` | `{nsteps: 200, dt: 0.001}` | `{nsteps: 400, dt: 0.0005}` |
| pressure_coupling | `{tau_p: 5.0}` | `{tau_p: 8.0}` | `{tau_p: 10.0}` |
| temperature_coupling | `{tau_t: 0.5}` | `{tau_t: 1.0}` | `{tau_t: 2.0}` |
| command_error | `{-maxwarn: 2}` | `{-maxwarn: 3}` | `{-maxwarn: 4}` |
| topology_mismatch | restore from `.bak`; regenerate topology | — | FATAL |
| missing_input | FATAL (caller must supply input) | — | — |

RETRYABLE budget per phase per cause is 3. WARNING retries do not consume
the RETRYABLE budget. The identical-command-and-parameter rule applies
to both tiers.
