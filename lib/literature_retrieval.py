"""Optional, evidence-only PaperQA integration for unsupported MD cases.

This module never changes a tutorial contract or invokes GROMACS.  It queries
only PDFs/text supplied in a run-local ``literature/`` directory and persists
the raw cited answer as an escalation record requiring explicit approval.
"""
from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import protocol_contract as PC
from lib import state as run_state


MAX_QUESTION_CHARS = 2000
LITERATURE_DIRNAME = "literature"
RECORDS_DIRNAME = "literature_queries"
_CITATION_RE = re.compile(r"\(([^()]{1,160}(?:pages?|p\.)[^()]*)\)")


class LiteratureRetrievalError(RuntimeError):
    pass


def paperqa_available() -> bool:
    return importlib.util.find_spec("paperqa") is not None


def corpus_path(workspace: Path) -> Path:
    return Path(workspace) / LITERATURE_DIRNAME


def _validate_question(question: str) -> str:
    question = str(question).strip()
    if not question:
        raise LiteratureRetrievalError("literature question is required")
    if len(question) > MAX_QUESTION_CHARS:
        raise LiteratureRetrievalError(f"literature question exceeds {MAX_QUESTION_CHARS} characters")
    return question


def _extract_citation_markers(answer: str) -> list[str]:
    """Keep PaperQA's inline markers verbatim; do not invent bibliographic IDs."""
    return list(dict.fromkeys(match.group(1).strip() for match in _CITATION_RE.finditer(answer)))


def query_local_corpus(workspace: Path, question: str,
                       proposed_change: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ask PaperQA about a run-local corpus and save an approval-only record."""
    workspace = Path(workspace)
    question = _validate_question(question)
    contract = PC.assert_valid(workspace)
    if contract is None:
        raise LiteratureRetrievalError("protocol contract is required before literature retrieval")
    corpus = corpus_path(workspace)
    if not corpus.is_dir() or not any(path.is_file() for path in corpus.rglob("*")):
        raise LiteratureRetrievalError(
            f"no local literature corpus; add permitted papers under {corpus}"
        )
    if not paperqa_available():
        raise LiteratureRetrievalError(
            "PaperQA2 is not installed; install the optional 'literature' dependency"
        )

    # PaperQA2's stable public synchronous interface.  It may use an external
    # LLM/embedding provider configured by the operator; those credentials are
    # deliberately not accepted over this API or persisted in the run record.
    from paperqa import Settings, ask  # type: ignore[import-not-found]
    try:
        response = ask(question, settings=Settings(temperature=0.0,
                                                    paper_directory=str(corpus)))
    except Exception as exc:
        raise LiteratureRetrievalError(f"PaperQA query failed: {exc}") from exc

    answer = str(response)
    record = {
        "schema_version": "1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": "paperqa2",
        "question": question,
        "corpus_path": LITERATURE_DIRNAME,
        "contract_sha256": contract["contract_sha256"],
        "answer": answer,
        "citation_markers": _extract_citation_markers(answer),
        "proposed_change": proposed_change or None,
        "execution_policy": "requires_user_approval",
        "contract_modified": False,
    }
    records = workspace / RECORDS_DIRNAME
    records.mkdir(parents=True, exist_ok=True)
    filename = f"query_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    record_path = records / filename
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    # State records provenance only.  The evidence itself remains an immutable
    # run artifact and cannot silently mutate builder or MDP settings.
    state_path = run_state.path(workspace)
    if state_path.exists():
        state = run_state.read(workspace)
        state.setdefault("literature_escalations", []).append({
            "record_path": str(record_path.relative_to(workspace)),
            "question": question,
            "contract_sha256": contract["contract_sha256"],
            "execution_policy": "requires_user_approval",
        })
        run_state.write(workspace, state)
    return {**record, "record_path": str(record_path.relative_to(workspace))}
