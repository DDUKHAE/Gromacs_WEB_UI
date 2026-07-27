# Related Work and Competitive Landscape

*Status: draft for JCIM/SoftwareX-target manuscript. Reused from
`docs/journal_readiness_evaluation.md` §1 (web-research subagent, 2026-07-08),
re-verified with citations below.*

## Comparison table

| Tool | Interface | Automation level | Publication venue |
|---|---|---|---|
| **CHARMM-GUI** | Web GUI (multi-step form wizard) | Deterministic template wizard — generates input files, does not execute or supervise a run | Jo et al., *J. Chem. Theory Comput.* 2016 (CHARMM-GUI Membrane Builder / Solution Builder lineage) |
| **WebGRO** | Web form + server-side execution | Fixed protocol, fully automated, no agentic reasoning | Hosted service (no primary peer-reviewed methods paper identified) |
| **MDWeb / MDMoby** | Web portal + web-service API | Pre-built "expert-emulating" setup/test-run/analysis pipeline | *Bioinformatics* 2012 |
| **BioBB / BioBB-Wfs** | Python library + web GUI | Scripted, parameterized reproducible workflows wrapping GROMACS/AmberTools | Andrio et al., *Sci. Data* 2019; BioExcel Building Blocks workflows, *Nucleic Acids Res.* 2022 (BioBB-Wfs) |
| **Making it Rain** | Jupyter/Google Colab notebooks | Fixed notebook-cell protocol targeting low-resource labs, OpenMM backend | Ribeiro et al., *J. Chem. Inf. Model.* 2021 |
| **HTMD / PlayMolecule** | Python API + web app | High-throughput scripted system preparation, adaptive sampling, MSM construction; web app exposes individual tools (e.g., pKa prediction) | Doerr et al., *J. Chem. Theory Comput.* 2016; PlayMolecule, *J. Chem. Inf. Model.* 2017 |
| **gmx_MMPBSA** | CLI + GUI | Post-hoc analysis (binding free energy from GROMACS trajectories); not a run-execution agent | Valdés-Tresanco et al., *J. Chem. Theory Comput.* 2021 |
| **MDCrow** | Python/CLI LLM agent (LangChain, 40+ tools) | Agentic LLM orchestration, primarily targets OpenMM | Ramsundar-affiliated team; *Mach. Learn.: Sci. Technol.* 2025; arXiv:2502.09565 |
| **DynaMate** | Python/CLI multi-agent LLM system | Agentic LLM orchestration; multi-agent autonomous GROMACS + AmberTools execution, MM/PBSA, runtime error correction | arXiv:2512.10034 |
| **JCIM 2024 LLM simulation-workflow paper** | Agentic framework | LLM designs and executes a simulation study loop | *J. Chem. Inf. Model.* 2024, DOI:10.1021/acs.jcim.4c01653 |
| **This work (GROMACS Web UI)** | Web GUI + LLM agent + live browser terminal | Agentic, tutorial-grounded; PDB upload → 6-step builder → LLM CLI executes tutorial protocol via GROMACS, with live command streaming, NGL 3D viewer, XVG plot gallery | Target: JCIM / SoftwareX (this manuscript) |

## Honest positioning statement

**Our contribution is not the first LLM-for-MD system.** That ground has already
been broken: DynaMate (arXiv:2512.10034) demonstrates a multi-agent LLM system
autonomously driving GROMACS and AmberTools end-to-end, including MM/PBSA
post-processing and runtime error correction; MDCrow (arXiv:2502.09565, *MLST*
2025) demonstrates a LangChain-based tool-using LLM agent across 40+ tools,
primarily for OpenMM; and a *J. Chem. Inf. Model.* 2024 paper
(DOI:10.1021/acs.jcim.4c01653) already describes an LLM-orchestrated simulation
workflow published in the same target venue. Any framing of this project as
"the first LLM applied to molecular dynamics" is factually false and would be
immediately falsifiable by a reviewer aware of this literature.

What none of the above tools — nor the deterministic web tools in the table
above (CHARMM-GUI, WebGRO, MDWeb, BioBB-Wfs, Making it Rain, HTMD/PlayMolecule)
— provide **simultaneously** is: a zero-install, browser-delivered interface to
an agentic LLM-driven MD loop, where the raw commands the agent issues are
streamed live to the user, the agent's execution is grounded in a curated
tutorial corpus rather than open-ended tool use, and the underlying LLM backend
is swappable across vendors within the same harness. Existing LLM-MD agents
(DynaMate, MDCrow) are local Python/CLI packages requiring installation and
command-line literacy; existing web-delivered MD tools (CHARMM-GUI, WebGRO,
BioBB-Wfs, MDWeb) are deterministic template/form wizards with no LLM
reasoning or agentic tool use inside the browser session. **Our contribution
is therefore not "the first LLM for MD" but the first system to deliver an
agentic, transparent, tutorial-grounded, model-agnostic MD execution harness
through a zero-install browser UI** — see
`docs/manuscript/novelty_statement.md` for the four differentiation axes and
their concrete code-level implementation.

## Citation list (with identifiers)

- **CHARMM-GUI** — Jo, S. et al. *J. Chem. Theory Comput.* 2016 (CHARMM-GUI input generator lineage).
- **BioBB-Wfs** — BioExcel Building Blocks workflows. *Nucleic Acids Res.* 2022.
- **Making it Rain** — Ribeiro, J. V. et al. *J. Chem. Inf. Model.* 2021.
- **MDCrow** — arXiv:2502.09565; *Mach. Learn.: Sci. Technol.* 2025.
- **DynaMate** — arXiv:2512.10034.
- **JCIM 2024 LLM simulation-workflow paper** — DOI:10.1021/acs.jcim.4c01653.
- **MDWeb/MDMoby** — *Bioinformatics* 2012.
- **HTMD / PlayMolecule** — Doerr, S. et al. *J. Chem. Theory Comput.* 2016; PlayMolecule, *J. Chem. Inf. Model.* 2017.
- **gmx_MMPBSA** — Valdés-Tresanco, M. S. et al. *J. Chem. Theory Comput.* 2021.

*Note: WebGRO's methods citation could not be independently confirmed as a
peer-reviewed publication during this pass; it is listed as a hosted service.
Confirm/replace before final submission if a primary reference exists.*
