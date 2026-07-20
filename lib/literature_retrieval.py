"""Evidence-only literature retrieval for unsupported MD cases.

This module never changes a tutorial contract or invokes GROMACS.  It queries
only a run-local ``literature/`` directory and persists raw cited answers as
escalation records requiring explicit approval.  ``search_open_evidence`` may
populate that directory with bibliographic metadata and abstracts returned by
the public Europe PMC API; it never downloads paywalled papers or executes a
proposed protocol change.
"""
from __future__ import annotations

import importlib.util
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import protocol_contract as PC
from lib import state as run_state


MAX_QUESTION_CHARS = 2000
MAX_SEARCH_CHARS = 500
MAX_SEARCH_RESULTS = 10
LITERATURE_DIRNAME = "literature"
RECORDS_DIRNAME = "literature_queries"
EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
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


def _open_json(url: str) -> dict[str, Any]:
    """Fetch JSON from the one allow-listed, public metadata endpoint."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise LiteratureRetrievalError(f"open literature search failed: {exc}") from exc


def _validate_search_query(query: str, limit: int) -> tuple[str, int]:
    query = str(query).strip()
    if not query:
        raise LiteratureRetrievalError("literature search query is required")
    if len(query) > MAX_SEARCH_CHARS:
        raise LiteratureRetrievalError(f"literature search query exceeds {MAX_SEARCH_CHARS} characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SEARCH_RESULTS:
        raise LiteratureRetrievalError(f"literature search limit must be between 1 and {MAX_SEARCH_RESULTS}")
    return query, limit


def _result_markdown(result: dict[str, Any]) -> tuple[str, str]:
    """Create an indexable, provenance-preserving document from an abstract."""
    source = str(result.get("source") or "MED")
    identifier = str(result.get("id") or "unknown")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"europepmc_{source}_{identifier}")
    title = str(result.get("title") or "Untitled record").strip()
    abstract = str(result.get("abstractText") or "").strip()
    authors = str(result.get("authorString") or "").strip()
    journal = str(result.get("journalTitle") or "").strip()
    year = str(result.get("pubYear") or "").strip()
    doi = str(result.get("doi") or "").strip()
    pmcid = str(result.get("pmcid") or "").strip()
    url = f"https://europepmc.org/article/{source}/{identifier}"
    lines = [
        "---",
        "retrieval_source: Europe PMC public API",
        f"source_id: {source}:{identifier}",
        f"record_url: {url}",
        f"retrieved_at_utc: {datetime.now(timezone.utc).isoformat()}",
        "content_scope: bibliographic metadata and abstract only",
        "license_status: not asserted; verify before using full text",
        "---",
        "",
        f"# {title}",
        "",
        f"Authors: {authors or 'not supplied'}",
        f"Journal: {journal or 'not supplied'} ({year or 'year not supplied'})",
        f"DOI: {doi or 'not supplied'}",
        f"PMCID: {pmcid or 'not supplied'}",
        f"Europe PMC: {url}",
        "",
        "## Abstract",
        abstract or "No abstract was returned by Europe PMC for this record.",
        "",
    ]
    return safe_name + ".md", "\n".join(lines)


def search_open_evidence(workspace: Path, query: str, limit: int = 5) -> dict[str, Any]:
    """Find public MD evidence and add only its indexable abstract records.

    The query is deliberately not an arbitrary URL fetch.  Europe PMC is
    allow-listed, full text is not downloaded, and all returned documents stay
    scoped to one run's corpus for subsequent PaperQA review.
    """
    workspace = Path(workspace)
    query, limit = _validate_search_query(query, limit)
    contract = PC.assert_valid(workspace)
    if contract is None:
        raise LiteratureRetrievalError("protocol contract is required before literature retrieval")
    params = urllib.parse.urlencode({"query": query, "format": "json", "resultType": "core", "pageSize": limit})
    payload = _open_json(f"{EUROPE_PMC_SEARCH_URL}?{params}")
    results = payload.get("resultList", {}).get("result", [])
    if not isinstance(results, list):
        raise LiteratureRetrievalError("open literature search returned an invalid result list")
    corpus = corpus_path(workspace)
    corpus.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, str]] = []
    for item in results[:limit]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        filename, content = _result_markdown(item)
        destination = corpus / filename
        destination.write_text(content, encoding="utf-8")
        saved.append({
            "source_id": f"{item.get('source', 'MED')}:{item['id']}",
            "title": str(item.get("title") or "Untitled record"),
            "record_path": str(destination.relative_to(workspace)),
            "record_url": f"https://europepmc.org/article/{item.get('source', 'MED')}/{item['id']}",
        })
    record = {
        "schema_version": "1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": "europe_pmc_public_metadata",
        "query": query,
        "contract_sha256": contract["contract_sha256"],
        "content_scope": "bibliographic metadata and abstracts only",
        "execution_policy": "requires_user_approval",
        "contract_modified": False,
        "results": saved,
    }
    records = workspace / RECORDS_DIRNAME
    records.mkdir(parents=True, exist_ok=True)
    record_path = records / f"search_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    state_path = run_state.path(workspace)
    if state_path.exists():
        state = run_state.read(workspace)
        state.setdefault("literature_escalations", []).append({
            "record_path": str(record_path.relative_to(workspace)),
            "query": query,
            "contract_sha256": contract["contract_sha256"],
            "execution_policy": "requires_user_approval",
        })
        run_state.write(workspace, state)
    return {**record, "record_path": str(record_path.relative_to(workspace))}


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
