# lib/xvg_parser.py
import re
import statistics
from pathlib import Path
from typing import Any

TITLE_RE = re.compile(r'@\s*title\s+"([^"]*)"')
XLAB_RE = re.compile(r'@\s*xaxis\s+label\s+"([^"]*)"')
YLAB_RE = re.compile(r'@\s*yaxis\s+label\s+"([^"]*)"')
LEGEND_RE = re.compile(r'@\s*s(\d+)\s+legend\s+"([^"]*)"')


def _read_metadata(lines: list[str]) -> dict[str, str]:
    meta = {"title": "", "xaxis_label": "", "yaxis_label": ""}
    for line in lines:
        if not line.startswith("@"):
            continue
        if m := TITLE_RE.search(line):
            meta["title"] = m.group(1)
        if m := XLAB_RE.search(line):
            meta["xaxis_label"] = m.group(1)
        if m := YLAB_RE.search(line):
            meta["yaxis_label"] = m.group(1)
    return meta


def _read_legends(lines: list[str]) -> list[str]:
    """Return per-series legend labels ordered by series index."""
    legends: dict[int, str] = {}
    for line in lines:
        if m := LEGEND_RE.search(line):
            legends[int(m.group(1))] = m.group(2)
    if not legends:
        return []
    return [legends.get(i, f"col {i + 1}") for i in range(max(legends) + 1)]


def _read_data(lines: list[str]) -> list[list[float]]:
    rows = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        parts = s.split()
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue
    if not rows:
        return []
    ncols = len(rows[0])
    return [[r[c] for r in rows if len(r) > c] for c in range(ncols)]


def _downsample(columns: list[list[float]], max_points: int) -> list[list[float]]:
    if not columns or len(columns[0]) <= max_points:
        return columns
    stride = max(1, len(columns[0]) // max_points)
    return [c[::stride][:max_points] for c in columns]


def _col_summary(y: list[float]) -> dict[str, float]:
    if not y:
        return {"count": 0}
    return {
        "count": len(y),
        "min": min(y),
        "max": max(y),
        "mean": statistics.mean(y),
        "std": statistics.pstdev(y) if len(y) > 1 else 0.0,
        "first": y[0],
        "last": y[-1],
    }


def parse_text(text: str, max_points: int = 1000) -> dict[str, Any]:
    """Parse XVG content from a string. Returns metadata, column labels, and downsampled columns."""
    lines = text.splitlines()
    meta = _read_metadata(lines)
    legends = _read_legends(lines)
    cols = _read_data(lines)
    cols = _downsample(cols, max_points)
    return {**meta, "column_labels": legends, "columns": cols}


def summary_all(text: str) -> list[dict[str, float]]:
    """Return summary statistics for each Y column (index 1..) in the XVG text."""
    lines = text.splitlines()
    cols = _read_data(lines)
    return [_col_summary(c) for c in cols[1:]]


def parse(path: Path, max_points: int = 1000) -> dict[str, Any]:
    return parse_text(Path(path).read_text(), max_points)


def summary(path: Path, column: int = 1) -> dict[str, float]:
    cols = _read_data(Path(path).read_text().splitlines())
    if len(cols) <= column:
        return {"count": 0}
    return _col_summary(cols[column])


def running_average(data: list[float], window: int) -> list[float]:
    """Return centered running average of data with the given window size."""
    if not data:
        return []
    half = window // 2
    result = []
    n = len(data)
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        chunk = data[start:end]
        result.append(sum(chunk) / len(chunk))
    return result
