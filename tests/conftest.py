import pytest
from pathlib import Path


@pytest.fixture
def ws_factory(tmp_path):
    """Return a factory that creates a valid run workspace under tmp_path/runs/."""
    def _make(run_id: str, files: dict[str, str | bytes] | None = None) -> tuple[Path, Path]:
        ws = tmp_path / "runs" / run_id
        ws.mkdir(parents=True)
        (ws / "state.json").write_text('{"status": "completed", "step": 8}')
        (ws / "runner.log").write_text("simulation completed\n")
        (ws / "inputs").mkdir()
        (ws / "inputs" / "input.pdb").write_text("ATOM      1  CA  ALA A   1      0.0   0.0   0.0\n")
        if files:
            for rel_path, content in files.items():
                target = ws / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    target.write_bytes(content)
                else:
                    target.write_text(content)
        return tmp_path, ws
    return _make


@pytest.fixture
def run_phase_grompp_args(tmp_path, monkeypatch):
    """Run md_runner.run_phase with gmx stubbed; return the grompp argv.

    Every phase's grompp command line -- -r for restraints, -t for the
    checkpoint, -n for a membrane index group, -maxwarn -- is decided inside
    run_phase, so the argv it hands GW.run is the only place to check them.
    """
    from lib import gmx_wrapper as GW
    from lib import state
    from skills.md_runner import md_runner as MR

    def _run(name, phase, overrides=None, variant="protein_aqueous_standard",
             has_protein=True, index=False, stage2_files=()):
        ws = tmp_path / name
        for sub in ("inputs", "stage1_env", "stage2_md", "stage3_viz"):
            (ws / sub).mkdir(parents=True)
        (ws / "stage1_env" / "ions.gro").write_text("gro")
        (ws / "stage1_env" / "topol.top").write_text("top")
        if index:
            (ws / "stage1_env" / "index.ndx").write_text("[ Protein_DPPC ]\n1\n")
        for fname in stage2_files:
            (ws / "stage2_md" / fname).write_text("gro")
        state.write(ws, state.initial(ws))
        s = state.read(ws)
        s["tutorial"] = {"id": "t", "variant": variant, "has_protein": has_protein}
        s["hardware"] = {"cpu_count": 1, "gpu_ids": [], "ntomp": 1}
        state.write(ws, s)

        captured = []

        def fake_run(args, cwd, **kwargs):
            if args[0] == "grompp":
                captured.append(list(args))
                Path(cwd, args[args.index("-o") + 1]).write_text("tpr")
            if args[0] == "mdrun":
                Path(cwd, f"{args[args.index('-deffnm') + 1]}.gro").write_text("gro")
            return GW.GmxResult(command=list(args), returncode=0, stdout="",
                                stderr="", classification="success")

        monkeypatch.setattr(GW, "run", fake_run)
        MR.run_phase(ws, phase, overrides)
        return ws, captured[0]
    return _run
