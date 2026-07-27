# Tutorial Preset Catalog Design

## Goal

Ship one loadable System Builder preset for each bundled tutorial. The values
must come from the bundled tutorial documentation, not generic application
defaults. A user should select a tutorial preset, supply the structure and any
required workflow files, then start a run without re-entering the documented
settings.

## Scope

- Add eight version-controlled JSON files beneath `presets/`.
- Use the existing preset API and the existing wizard load control; do not add
  a second preset endpoint or storage format.
- Retain user-created presets and their existing save/delete behaviour.
- Include a human-readable `notes` block in every catalog entry. It records
  required non-PDB inputs and the source tutorial constraints that cannot be
  represented by the current System Builder fields.

## Data Format

Each file is named `tutorial-<tutorial-id>.json` and is a System Builder config
document, rather than an API wrapper. This matches the value returned today by
`GET /api/presets` and consumed as `preset.config` by `wizardLoadPreset`.

The wizard-applied fields are:

- `forcefield.name`, `forcefield.water_model`
- `box.type`, `box.edge_distance_nm`
- `ions.salt_type`, `ions.concentration_M`, `ions.neutralize`
- expert-mode `simulation.temperature_K`, `pressure_bar`, `sim_time_ns`,
  `thermostat`, and `barostat`

`notes` is preserved in the JSON catalogue but is not treated as an executable
GROMACS setting. It provides traceability and tells the user which topology,
coordinates, index, or lambda files remain mandatory.

## Values and Sources

Only values stated by a tutorial are encoded. If a tutorial does not state a
value that the System Builder exposes, the preset uses the minimum neutral
wizard value and calls it out in `notes` as a UI limitation rather than
presenting it as a tutorial result. Advanced workflows retain their required
file manifests and JSON fields; loading a preset does not manufacture those
files.

## Error Handling

The current runner remains the authority for file/configuration validation.
The implementation will add tests that every catalog file parses, has all
wizard-required fields, and retains the tutorial-specific input requirements
in `notes`. It will also verify the preset endpoint lists catalog files.

## Non-goals

- No automatic generation of umbrella windows, lambda schedules, ligand
  parameters, membrane systems, or virtual-site topologies.
- No alteration of the simulation protocol merely to fit a missing tutorial
  value into a wizard field.
- No deletion or overwrite of user-created presets.
