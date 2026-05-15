# lib/xvg_parser.py
import re
import statistics
from pathlib import Path
from typing import Any

TITLE_RE = re.compile(r'@\s*title\s+"([^"]*)"')
XLAB_RE = re.compile(r'@\s*xaxis\s+label\s+"([^"]*)"')
YLAB_RE = re.compile(r'@\s*yaxis\s+label\s+"([^"]*)"')


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


def _read_data(lines: list[str]) -> list[list[float]]:
    rows = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        parts = s.split()
        rows.append([float(x) for x in parts])
    if not rows:
        return []
    ncols = len(rows[0])
    return [[r[c] for r in rows] for c in range(ncols)]


def _downsample(columns: list[list[float]], max_points: int) -> list[list[float]]:
    if not columns or len(columns[0]) <= max_points:
        return columns
    stride = max(1, len(columns[0]) // max_points)
    return [c[::stride][:max_points] for c in columns]


def parse(path: Path, max_points: int = 1000) -> dict[str, Any]:
    lines = Path(path).read_text().splitlines()
    meta = _read_metadata(lines)
    cols = _read_data(lines)
    cols = _downsample(cols, max_points)
    return {**meta, "columns": cols}


def summary(path: Path, column: int = 1) -> dict[str, float]:
    cols = _read_data(Path(path).read_text().splitlines())
    if len(cols) <= column:
        return {"count": 0}
    y = cols[column]
    return {
        "count": len(y),
        "min": min(y),
        "max": max(y),
        "mean": statistics.mean(y),
        "std": statistics.pstdev(y) if len(y) > 1 else 0.0,
        "first": y[0],
        "last": y[-1],
    }
