# Render Recipes

| Renderer | Detection | Command |
|---|---|---|
| PyMOL | `shutil.which("pymol")` | `pymol -cq render.pml` |
| VMD | `shutil.which("vmd")` | `vmd -dispdev text -e render.vmd` |
| Fallback | neither installed | no frame rendered, plot-only report |

PyMOL script template (`_PYMOL_SCRIPT` in `illustrator.py`) supplies the
default cartoon + surface + key-residue close-up. Override the
`highlight_resi` parameter from `render_frame()` to focus on a binding
pocket or membrane cross-section.
