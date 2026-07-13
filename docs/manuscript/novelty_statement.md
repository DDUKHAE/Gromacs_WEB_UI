# Novelty Statement — Four Differentiation Axes

As established in `docs/manuscript/related_work.md`, this project is **not**
the first LLM-driven MD system (DynaMate, arXiv:2512.10034; MDCrow,
arXiv:2502.09565; JCIM 2024, DOI:10.1021/acs.jcim.4c01653 all precede it). The
defensible, publishable novelty is the specific *combination* below, which no
prior tool provides simultaneously. Each axis is mapped to the concrete code
that implements it, so the claim is falsifiable against the repository rather
than asserted in prose alone.

## Axis 1 — Zero-install, browser-delivered agentic loop

**Claim:** The agentic LLM-driven MD loop (prompt → tool calls → `gmx`
execution → result inspection) runs entirely behind a hosted browser UI; the
user never installs or invokes a CLI package directly. Prior LLM-MD agents
(DynaMate, MDCrow) are local Python/CLI packages; prior web-delivered MD tools
(CHARMM-GUI, WebGRO, BioBB-Wfs, MDWeb) are deterministic wizards with no
in-session LLM reasoning.

**Implementing code:**
- `web/server.py` — FastAPI app serving the single-page UI and the run
  lifecycle API (`api_create_run` and related endpoints); the LLM CLI is
  spawned server-side, not by the end user.
- `web/llm_runner.py` — spawns the selected LLM CLI (Claude Code / Codex /
  Gemini) as a subprocess/PTY on behalf of the browser session.
- `web/static/index.html` — the single browser artifact through which the
  entire builder → run → analysis flow is driven; no local install beyond a
  browser is required on the client side.

## Axis 2 — Execution transparency (live `gmx` command streaming)

**Claim:** The raw commands the LLM agent issues (including every `gmx`
invocation) are streamed live to the browser over a WebSocket into an
xterm.js terminal, rather than being summarized, hidden, or post-hoc logged.
This is a direct, structural answer to the "LLM black box" objection and is
listed as a top novelty axis in the competitive-landscape review
(`docs/journal_readiness_evaluation.md` §1.2, item 2).

**Implementing code:**
- `web/server.py:586` (`@app.websocket("/ws/runs/{run_id}")`, `ws_terminal`) —
  bidirectional PTY proxy: bytes from the LLM CLI's pseudo-terminal are
  forwarded to the browser socket in real time (`websocket.send_bytes(data)`),
  and browser keystrokes (e.g., approval `y`/`n`) are written back to the PTY.
- PTY creation and reader-thread plumbing (`pty.openpty`, daemon reader thread
  → `call_soon_threadsafe`) referenced in the architecture review
  (`docs/journal_readiness_evaluation.md` §3.1) persist ANSI-stripped
  transcripts so a reconnecting client can replay the session history
  (`websocket.send_bytes(history)` at reconnect, `web/server.py:605`).
- `web/static/index.html` — embeds a bundled xterm.js terminal (`term.onData
  → ws.send`) as the live command-stream renderer.

**Caveat (for honest framing):** transparency here means the operator can
*see* every command as it is issued; it is not (yet) a structural guarantee
that the agent cannot deviate from the tutorial protocol — see
`docs/journal_readiness_evaluation.md` §2.4 for the current limits of
config-audit enforcement (`lib/system_config_validator.py`).

## Axis 3 — Tutorial-grounded (RAG-like) execution

**Claim:** Rather than giving the LLM open-ended tool access (as MDCrow does
with 40+ LangChain tools) or relying on the model's implicit MD knowledge, the
agent is routed to and grounded in a specific, versioned tutorial corpus
checked into the repository, and the state machine records which tutorial and
protocol variant is in force for the run.

**Implementing code:**
- `lib/tutorial_registry.py` — `route()` and `load_manifest()` select a
  tutorial id from the prompt text and PDB-derived structural hints
  (`_pdb_match`, `_prompt_match`), reading `docs/tutorial/tutorial_index.json`.
- `docs/tutorial/<tutorial_id>/` — per-tutorial directories (e.g.
  `Lysozyme_in_water`, `Free_Energy_Calculations_Methane_in_Water`,
  `KALP15_in_DPPC`, `Protein_Ligand_Complex`) each with a
  `tutorial.manifest.json` plus staged markdown documentation
  (`theory_and_topology`, `energy_minimization`, `production_MD`, `analysis`,
  etc.) that the LLM is instructed to follow step by step.
- `skills/env_builder/env_builder.py:70` (`select_tutorial`) — persists the
  routing decision (`tutorial.id`, `tutorial.variant`,
  `tutorial.manifest_path`) into the run's `state.json` so the grounding
  document set is fixed and auditable for the lifetime of the run.
- `lib/tutorial_auditor.py` — cross-checks the run's actual configuration
  against per-tutorial expected values (`_TUTORIAL_EXPECTATIONS`), tying the
  grounding claim to a (partial, see Limitations) post-hoc audit.

**Contrast with DynaMate:** DynaMate grounds its agents in literature/document
corpora generally; this project grounds execution specifically in canonical,
versioned GROMACS tutorial protocols bundled with the repository, favoring
protocol fidelity over open-ended literature retrieval.

## Axis 4 — Model-agnostic backend (cross-model reliability benchmarking)

**Claim:** The LLM backend is swappable behind a common adapter interface
(Claude Code, OpenAI Codex CLI, Gemini CLI), which is not a design goal of
DynaMate or MDCrow (each tied to a specific agent framework/model family).
This enables — but as of this writing does not yet include — a built-in
cross-model reliability/success-rate comparison, flagged as a reviewer
expectation in `docs/journal_readiness_evaluation.md` §1.3.

**Implementing code:**
- `web/llm_adapters/base.py` — `LLMAdapter` interface (`name`, `cli`,
  `build_command`) that each backend implements.
- `web/llm_adapters/claude.py` — `ClaudeAdapter.build_command`: invokes
  `claude` (optionally `--dangerously-skip-permissions` for auto-approve).
- `web/llm_adapters/codex.py` — `CodexAdapter.build_command`: invokes `codex
  --approval-mode full-auto` or `suggest`.
- `web/llm_adapters/gemini.py` — `GeminiAdapter.build_command`: invokes the
  Gemini CLI (`agy --auto-accept`; flag marked `TODO: confirm exact
  auto-approve flag` — unresolved as of this writing, see Limitations).
- `scripts/collect_metrics.py` (per `docs/journal_readiness_evaluation.md`
  §2.5) already measures completion rate/time/first-failure-step per run and
  could be extended, run per backend, into the cross-model reliability table
  a JCIM-level review would expect.

**Limitations (honest framing, not to be omitted from the manuscript):**
- The Gemini adapter's auto-approve flag is unverified (`# TODO` in
  `web/llm_adapters/gemini.py`).
- No cross-model benchmark currently exists in the repository; Axis 4 today
  is an architectural affordance ("the backend is swappable"), not yet a
  demonstrated empirical result. The manuscript must not claim a completed
  cross-model study until `scripts/collect_metrics.py` (or successor) is run
  across all three backends and the results are reported.
- Tutorial grounding (Axis 3) and execution transparency (Axis 2) do not
  currently constitute a structural guarantee against protocol deviation —
  the LLM can still write files or run commands outside the tutorial's
  intended parameters, subject only to the partial config audit described in
  `docs/journal_readiness_evaluation.md` §2.4.

## Summary framing for the manuscript

"This work is not the first application of LLMs to molecular dynamics
(DynaMate, MDCrow, and a 2024 JCIM paper precede it). Its contribution is an
interactive, transparent, browser-delivered agent harness that is
tutorial-grounded and model-agnostic — a combination not previously
demonstrated — enabling both non-CLI-literate users to observe and steer an
agentic MD run in real time, and researchers to compare LLM backends on
identical, protocol-grounded MD tasks."
