# Run Failure Summary

When a run is `failed` or `aborted`, the run API will return a concise
`failure_summary` with `stage`, `cause`, and `next_action`. The server derives
it from persisted state: retry history first, then the final runner log line,
then the last completed stage. The browser renders the summary as a visible
failure panel on the run view. It does not parse terminal output itself and it
does not expose full raw logs by default.

Known retry causes map to actionable Korean guidance: pressure coupling,
temperature coupling, unstable energy, command/preprocessing error, and an
unknown fallback. Missing state or logs must still return an explicit unknown
summary rather than silently hiding the failure.

Tests cover a retry-history-derived summary, a log-derived fallback, and the
failed-run API payload. Existing successful-run payloads remain unchanged.
