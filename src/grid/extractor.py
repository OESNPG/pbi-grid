"""
Extract a layout.yaml from an existing PBIR report.

Algorithm
---------
1. For each page, collect all visuals with their absolute positions.
2. Cluster y-start values (within CLUSTER_TOL units) to identify row bands.
3. Assign each visual to its starting row band and compute:
   - span  = round(width / col_unit), clamped to [1, 12]
   - rowspan = number of row bands the visual covers
4. Within each row, sort visuals by x.
5. Emit a YAML dict with real visual names (PBIR IDs) and inferred spans.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from ..models import Report, Visual

_GRID_COLUMNS = 12
_CLUSTER_TOL = 5.0  # canvas units below which two y values are the same row


# ── Row-band inference ──────────────────────────────────────────────────────────

def _cluster_y(values: list[float]) -> list[float]:
    """Return sorted unique row-start y values after clustering near-identical values."""
    clusters: list[float] = []
    for v in sorted(set(values)):
        if not clusters or v - clusters[-1] > _CLUSTER_TOL:
            clusters.append(v)
    return clusters


def _row_heights(row_starts: list[float], canvas_height: int) -> list[float]:
    heights: list[float] = []
    for i, start in enumerate(row_starts):
        next_start = row_starts[i + 1] if i + 1 < len(row_starts) else canvas_height
        heights.append(next_start - start)
    return heights


def _find_row_idx(y: float, row_starts: list[float]) -> int:
    best_i, best_d = 0, abs(y - row_starts[0])
    for i, start in enumerate(row_starts[1:], 1):
        d = abs(y - start)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def _infer_rowspan(
    visual_y: float,
    visual_height: float,
    row_idx: int,
    row_starts: list[float],
    row_heights: list[float],
) -> int:
    bottom = visual_y + visual_height
    cumulative = row_starts[row_idx]
    for i in range(row_idx, len(row_heights)):
        cumulative += row_heights[i]
        if cumulative >= bottom - _CLUSTER_TOL:
            return i - row_idx + 1
    return len(row_heights) - row_idx


def _infer_span(width: float, col_unit: float) -> int:
    return max(1, min(_GRID_COLUMNS, round(width / col_unit)))


# ── Page layout inference ───────────────────────────────────────────────────────

def _infer_page_rows(
    visuals: list[Visual],
    canvas_width: int,
    canvas_height: int,
) -> list[dict[str, Any]]:
    col_unit = canvas_width / _GRID_COLUMNS

    row_starts = _cluster_y([v.position.y for v in visuals])
    row_hts = _row_heights(row_starts, canvas_height)

    # Bin each visual into its starting row.
    bins: dict[int, list[Visual]] = {i: [] for i in range(len(row_starts))}
    for v in visuals:
        bins[_find_row_idx(v.position.y, row_starts)].append(v)

    rows: list[dict[str, Any]] = []
    for row_idx, row_visuals in bins.items():
        if not row_visuals:
            continue

        row_visuals.sort(key=lambda v: v.position.x)
        height = math.ceil(row_hts[row_idx])

        cols: list[dict[str, Any]] = []
        for v in row_visuals:
            span = _infer_span(v.position.width, col_unit)
            rowspan = _infer_rowspan(
                v.position.y, v.position.height,
                row_idx, row_starts, row_hts,
            )
            col: dict[str, Any] = {
                "span": span,
                "name": v.name,
                "visual": v.visual_type,
            }
            if rowspan > 1:
                col["rowspan"] = rowspan
            cols.append(col)

        rows.append({
            "id": f"row{row_idx}",
            "height": height,
            "cols": cols,
        })

    return rows


# ── Public API ──────────────────────────────────────────────────────────────────

def extract(
    report_path: Path,
    output: Path | None = None,
    merge_with: Path | None = None,
) -> Path:
    """Read *report_path* (.Report folder) and generate a layout.yaml.

    Parameters
    ----------
    report_path :
        Path to the .Report folder.
    output :
        Destination file. Defaults to ``<report_parent>/<ReportName>_layout.yaml``.
    merge_with :
        Path to an existing layout YAML. Pages already present in that file are
        kept verbatim (preserving component definitions, menu configs, etc.).
        Only pages found in the report but *missing* from the existing YAML are
        extracted and appended. The page order follows the report's page order.
    """
    report = Report.from_pbir(report_path)

    # Load existing page configs keyed by page ID so we can preserve them.
    existing_pages: dict[str, dict[str, Any]] = {}
    existing_top: dict[str, Any] = {}
    if merge_with and merge_with.exists():
        existing_top = yaml.safe_load(merge_with.read_text(encoding="utf-8")) or {}
        for page in existing_top.get("pages", []):
            existing_pages[page["id"]] = page

    pages_data: list[dict[str, Any]] = []
    for page in report.pages:
        if page.name in existing_pages:
            # Preserve the existing config (component definitions, menu items, etc.)
            pages_data.append(existing_pages[page.name])
        else:
            rows = _infer_page_rows(page.visuals, page.width, page.height)
            pages_data.append({
                "id": page.name,
                "display_name": page.display_name,
                "rows": rows,
            })

    if output is None:
        output = report_path.parent / f"{report.name}_layout.yaml"

    import os
    source_rel = os.path.relpath(report_path.resolve(), output.parent.resolve())

    # Preserve top-level keys from existing file (report name, canvas, etc.)
    # but always refresh the source path and pages list.
    layout: dict[str, Any] = {
        "report": existing_top.get("report", {"name": report.name}) | {"source": source_rel},
        "canvas": existing_top.get("canvas", {
            "width": report.pages[0].width if report.pages else 1280,
            "height": report.pages[0].height if report.pages else 720,
            "gutter": 0,
        }),
        "pages": pages_data,
    }

    output.write_text(
        yaml.dump(layout, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return output
