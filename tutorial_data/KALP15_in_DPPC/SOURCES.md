# KALP-15 in DPPC — input file provenance

Downloaded 2026-08-07 for testing the `KALP15_in_DPPC` tutorial.

## From mdtutorials.com (Justin Lemkul)

Base: `http://www.mdtutorials.com/gmx/2018/membrane_protein/Files/`

| File | Bytes | Notes |
|---|---|---|
| `KALP-15_princ.pdb` | 16,840 | Already present in the repo; verified byte-identical to upstream |
| `mdp/minim.mdp` | 932 | |
| `mdp/nvt.mdp` | 2,325 | |
| `mdp/npt.mdp` | 2,559 | |
| `mdp/md.mdp` | 2,470 | |
| `inflategro.pl` | 14,871 | Bilayer packing helper |
| `water_deletor.pl` | 6,823 | Removes waters trapped in the bilayer |

The `.mdp` files match the settings recorded in
`presets/tutorial-KALP15_in_DPPC.json`: `ref_t = 323`, `rvdw = rcoulomb = 1.2`,
`tc-grps = Protein_DPPC Water_and_ions`, `pcoupltype = semiisotropic`,
`nsteps = 500000 × 2 fs` (1 ns).

## Berger lipid files — via the Internet Archive

These three are **not** on mdtutorials. The tutorial points to D. Peter
Tieleman's distribution page, which is no longer served:

- `https://people.ucalgary.ca/~tieleman/download.html` — TLS certificate expired
- `http://people.ucalgary.ca/~tieleman/download.html` — HTTP 403
- `http://moose.bio.ucalgary.ca/…` — now redirects to a UCalgary site with no downloads

They were therefore taken from Internet Archive snapshots of Tieleman's own
`files/` directory (the `id_` suffix returns the original bytes, unmodified):

    https://web.archive.org/web/2018id_/http://people.ucalgary.ca/~tieleman/files/<name>

| File | Bytes | Verified |
|---|---|---|
| `dppc128.pdb` | 1,163,641 | 128 `DPP` + 3655 `SOL` residues, matching its own HEADER |
| `dppc.itp` | 12,772 | `[moleculetype] DPPC`, 50 atoms / 49 bonds / 57 angles / 47 dihedrals / 29 pairs |
| `lipid.itp` | 34,366 | Berger/GROMOS mixture; `[dihedraltypes]` function code 3 (Ryckaert-Bellemans); has `[pairtypes]` |

### Why these are the right files

`dppc128.pdb` carries `CRYST1 64.184 64.435 65.965` Å = 6.4184 / 6.4435 /
6.5965 nm, which is exactly the box the tutorial hardcodes in
`define_box_and_solvate`:

    gmx editconf -f KALP-15_processed.gro -o KALP_newbox.gro -c -box 6.41840 6.44350 6.59650

Every one of the 12 atom types referenced by `dppc.itp` resolves against
`lipid.itp`'s `[atomtypes]`, and the Ryckaert-Bellemans dihedrals match what
`generate_topology/modify_the_topology.md` describes.

## Still required before a run — not downloadable

The tutorial has you hand-build a modified force field, so this cannot be
fetched. From `generate_topology/modify_the_topology.md`:

1. Copy `$GMXLIB/gromos53a6.ff/` to `gromos53a6_lipid.ff/`
2. Merge `lipid.itp`'s `[atomtypes]` into `ffnonbonded.itp`, adding an `at.num` column
3. Merge `[nonbond_params]`, then delete the `;; parameters for lipid-GROMOS
   interactions` block and everything after it in that section
4. Drop (or rename to `H`) every `HW` line in `[nonbond_params]`
5. Merge `[pairtypes]` into `ffnonbonded.itp`
6. Append `[dihedraltypes]` to `ffbonded.itp`

`strong_posre.itp` is generated during the run (`genrestr`), not downloaded.

## Automation notes

`lib/berger_forcefield.py` performs the force-field preparation
(`docs/tutorial/KALP15_in_DPPC/generate_topology/modify_the_topology.md`).
`skills/env_builder` calls it whenever a run supplies `inputs/lipid.itp`.

### The force field is built per-run, not installed into $GMXLIB

The tutorial notes that placing `gromos53a6_lipid.ff` in `$GMXLIB` makes it
available system-wide. This project deliberately builds it into the run's
`stage1_env/` instead, which is `pdb2gmx`'s working directory and therefore
searched before `$GMXLIB`. The reasons:

- the exact parameters a run used stay archived inside that run
- the shared GROMACS install is never mutated, so two runs cannot disagree
  about what `gromos53a6_lipid` means
- nothing has to be uninstalled to reproduce a different lipid set

If you do want it system-wide, copy `stage1_env/gromos53a6_lipid.ff` into
`$GMXLIB` yourself; the build is a plain directory.

### `lipid.itp` may be raw or already prepared

Both forms are accepted and produce an equivalent force field:

| Input | `[nonbond_params]` merged | Notes |
|---|---|---|
| upstream `lipid.itp` | 90 | `HW` rows deleted |
| `lipid.prepared-manual.itp` | 102 | `HW` renamed to `H` |

The tutorial offers deletion and renaming as alternatives for the `HW` rows.
They are equivalent because GROMOS53a6's own `H` type has `c6 = c12 = 0`, so
the combination rule yields zero exactly as the explicit zero rows do. (`HC`
is *not* zero — renaming `HW` to `HC` would change the physics.)

A file whose lipid-GROMOS *marker* was deleted while its *rows* remain is
rejected rather than treated as prepared, since merging it would silently keep
parameters the tutorial removes.

### Scientific caveat carried over from the tutorial

GROMOS96 53A6 destabilises α-helices over long trajectories, and KALP-15 is a
transmembrane α-helix. The 1 ns production run in
`presets/tutorial-KALP15_in_DPPC.json` is short enough that this is not
expected to show, but a longer run should consider GROMOS96 54A7 or another
force field. Validating the model remains the researcher's responsibility —
Berger lipids mix GROMOS and OPLS-UA elements, and the combination used here is
the one the tutorial reports as tested.

### The troubleshooting page

`advanced_troubleshooting.html` has no counterpart in the local docs, so its
content is reproduced at
`docs/tutorial/KALP15_in_DPPC/troubleshooting/advanced_troubleshooting.md`.
Its two support files, `lipid_posre.itp` and `anneal_npt.mdp`, were downloaded
from `http://www.mdtutorials.com/gmx/2018/membrane_protein/Files/` and live here as
reference copies only — neither is staged into a run's `stage1_env/` by
`skills/env_builder`, and `anneal_npt.mdp`'s annealing block still needs to be
trimmed to two values per `tc_grps` before it will pass `grompp`. See the
troubleshooting page for what that means in practice.
