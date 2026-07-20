# PaperQA Literature Escalation

PaperQA2 is an optional evidence-retrieval layer for cases not covered by a
selected tutorial: nonstandard ligands, metal sites, unusual force fields, or
special sampling protocols. It is **not** part of the normal MD pipeline and
can never modify `protocol_contract.json`, MDP files, or a running simulation.

## Setup

Install only when literature escalation is required:

```bash
pip install -e '.[literature]'
```

PaperQA2 requires Python 3.11+ and an operator-configured LLM/embedding
provider (or local equivalent). Do not submit provider credentials through the
web UI. Place papers the project is allowed to index under the run-local
`literature/` directory.

## Query contract

`POST /api/runs/{run_id}/literature/query` accepts a question and an optional
descriptive `proposed_change` object. It accepts neither URLs nor filesystem
paths. The response is written as `literature_queries/query_*.json` and records
the raw PaperQA answer, inline citation markers, corpus location, timestamp,
and the active protocol-contract hash.

Every result has `execution_policy: requires_user_approval`. A cited answer is
evidence for designing a new manifest or an explicitly experimental contract;
it is never permission for an agent to change a standard tutorial run.
