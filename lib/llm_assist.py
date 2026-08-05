"""Auxiliary LLM checkpoints — structured, single-shot judgment calls that
replace the interactive-agent decisions that used to require a human (or a
hung PTY session) watching pipeline output and deciding whether to proceed.

Every call here is optional: if no API key is configured or the API call
fails for any reason, callers fall back to their existing rule-based
behavior. The LLM never blocks the pipeline.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel

MODEL = "claude-haiku-4-5"
_TIMEOUT_S = 30.0

log = logging.getLogger(__name__)


class CheckpointVerdict(BaseModel):
    proceed: bool
    diagnosis: str


class PhaseVerdict(BaseModel):
    proceed: bool
    accept_mutation: bool
    diagnosis: str


def client_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _client():
    import anthropic
    return anthropic.Anthropic().with_options(timeout=_TIMEOUT_S)


def review_pdb(pdb_flags: dict[str, Any], pdb_summary: dict[str, Any]) -> CheckpointVerdict:
    if not client_available():
        return CheckpointVerdict(proceed=True, diagnosis="LLM unavailable; proceeding without review.")
    try:
        response = _client().messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You are a molecular dynamics QA reviewer. A PDB structure was "
                "flagged by a deterministic analyzer before topology generation. "
                "Decide whether the GROMACS pipeline should proceed to build the "
                "simulation topology from this structure as-is, or stop for human "
                "review. Be conservative: only recommend stopping for issues that "
                "would produce a scientifically invalid or non-simulatable system "
                "(e.g. large unmodeled gaps, ambiguous disulfides that change "
                "connectivity). Minor, commonly-handled issues should proceed."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Flagged issues: {pdb_flags}\n\n"
                    f"Full structure summary: {pdb_summary}"
                ),
            }],
            output_format=CheckpointVerdict,
        )
        return response.parsed_output
    except Exception:
        log.warning("review_pdb: LLM call failed, proceeding without review", exc_info=True)
        return CheckpointVerdict(proceed=True, diagnosis="LLM call failed; proceeding without review.")


def review_gro(judgment: dict[str, Any]) -> CheckpointVerdict:
    if not client_available():
        return CheckpointVerdict(proceed=True, diagnosis="LLM unavailable; proceeding without review.")
    try:
        response = _client().messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You are a molecular dynamics QA reviewer. After solvating and "
                "ionizing a GROMACS system, a deterministic neutrality check "
                "returned a non-pass judgment. Decide whether the pipeline should "
                "proceed to energy minimization with the current ionized "
                "structure as-is, or stop for human review. Be conservative: "
                "only recommend stopping if the residual charge is large enough "
                "to invalidate electrostatics for the simulation's purpose."
            ),
            messages=[{
                "role": "user",
                "content": f"Neutrality judgment: {judgment}",
            }],
            output_format=CheckpointVerdict,
        )
        return response.parsed_output
    except Exception:
        log.warning("review_gro: LLM call failed, proceeding without review", exc_info=True)
        return CheckpointVerdict(proceed=True, diagnosis="LLM call failed; proceeding without review.")


def review_md_phase(phase: str, judgment: dict[str, Any], xvg_summary: dict[str, Any],
                    mdp_settings: dict[str, Any]) -> PhaseVerdict:
    if not client_available():
        return PhaseVerdict(proceed=True, accept_mutation=False,
                            diagnosis="LLM unavailable; proceeding without review.")
    try:
        response = _client().messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You are a molecular dynamics QA reviewer. A GROMACS MD phase "
                "just finished and a deterministic validator judged it. Decide "
                "whether the pipeline should proceed to the next phase. If the "
                "judgment tier is 'warning', a suggested_mutation may be present "
                "inside the judgment — decide whether to accept it (retry this "
                "phase with the suggested parameter change applied) or decline "
                "(proceed as-is). Be conservative: only recommend stopping "
                "(proceed=false) if the phase's numbers indicate the system is "
                "not physically sound to continue from."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Phase: {phase}\n"
                    f"Judgment: {judgment}\n"
                    f"Metric summary: {xvg_summary}\n"
                    f"MDP overrides used for this attempt: {mdp_settings}"
                ),
            }],
            output_format=PhaseVerdict,
        )
        return response.parsed_output
    except Exception:
        log.warning("review_md_phase: LLM call failed, proceeding without review", exc_info=True)
        return PhaseVerdict(proceed=True, accept_mutation=False,
                            diagnosis="LLM call failed; proceeding without review.")
