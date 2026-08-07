---
name: illustrator
description: >-
  Analyze, plot, render, animate, and report on a completed MD trajectory.
  Runs the full analysis catalog (RMSD, RMSF, gyrate, SASA, hbond, dssp,
  energy, PCA, plus tutorial-specific PMF/BAR analyses).
  Produces matplotlib plots, PyMOL/VMD structural renders (with graceful
  degradation), ffmpeg trajectory animations, and a markdown report.
  Outputs to workspace/stage3_viz/. Invoke when md-runner has completed,
  or when the user supplies an existing trajectory.
metadata:
  version: 1.0.0
compatibility: "Claude Code, GPT Agent, Cursor, Antigravity"
---

# Skill: illustrator

## Entry Point

```python
from skills.illustrator.illustrator import illustrate
illustrate(workspace_dir, interactive=False)
```

## Input Schema

```json
{
  "workspace_dir": "/abs/path/workspace",
  "render_frames": [0, "middle", "last"],
  "animation": {"enabled": true, "fps": 30, "stride": 10, "formats": ["mp4"]},
  "interactive": true
}
```

## Output Contract

Files under `workspace/stage3_viz/`:
- `*.xvg` for every analysis
- `*.png` for every plot
- `frame_*.png` for each rendered frame
- `trajectory.mp4` (or `.gif`) for animation

`workspace/state.json` is updated with
`step_outputs.step_8.{analysis_summaries, advanced_summaries,
variant_summary}` and `last_completed_stage="viz"`.

## Graceful Degradation

- PyMOL absent → VMD attempted → matplotlib-only.
- ffmpeg absent → animation skipped (plots and renders still produced).

## References

- `references/analysis_recipes.md`
- `references/render_recipes.md`
- `references/animation_recipes.md`
