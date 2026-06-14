"""Extract a layout.yaml from an existing PBIR report.

Algorithm
---------
1. For each page, collect all visuals with their absolute positions.
2. Cluster y-start values (within CLUSTER_TOL units) to identify row bands.
3. Assign each visual to its starting row band and compute:
   - span = round(width / col_unit), clamped to [1, 12]
   rowspan is intentionally not inferred — it is a layout design decision
   left to the user or set by scaffold for components (menu, header, footer).
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
    """Return sorted unique row-start y values after merging near-identical values."""
    clusters: list[float] = []
    for v in sorted(set(values)):
        if not clusters or v - clusters[-1] > _CLUSTER_TOL:
            clusters.append(v)
    return clusters


def _row_heights(row_starts: list[float], canvas_height: int) -> list[float]:
    """Compute pixel height of each row band from consecutive y-start values."""
    heights: list[float] = []
    for i, start in enumerate(row_starts):
        next_start = row_starts[i + 1] if i + 1 < len(row_starts) else canvas_height
        heights.append(next_start - start)
    return heights


def _find_row_idx(y: float, row_starts: list[float]) -> int:
    """Return the index of the row band whose y-start is closest to *y*."""
    best_i, best_d = 0, abs(y - row_starts[0])
    for i, start in enumerate(row_starts[1:], 1):
        d = abs(y - start)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def _infer_span(width: float, col_unit: float) -> int:
    """Round visual width to the nearest grid span, clamped to [1, 12]."""
    return max(1, min(_GRID_COLUMNS, round(width / col_unit)))


# ── Page layout inference ───────────────────────────────────────────────────────

def _infer_page_rows(
    visuals: list[Visual],
    canvas_width: int,
    canvas_height: int,
) -> list[dict[str, Any]]:
    """Infer grid rows and col spans from the absolute positions of page visuals."""
    col_unit = canvas_width / _GRID_COLUMNS

    row_starts = _cluster_y([v.position.y for v in visuals])
    row_hts = _row_heights(row_starts, canvas_height)

    bins: dict[int, list[Visual]] = {i: [] for i in range(len(row_starts))}
    for v in visuals:
        bins[_find_row_idx(v.position.y, row_starts)].append(v)

    rows: list[dict[str, Any]] = []
    for row_idx, row_visuals in bins.items():
        if not row_visuals:
            continue
        row_visuals.sort(key=lambda v: v.position.x)
        cols: list[dict[str, Any]] = [
            {"span": _infer_span(v.position.width, col_unit), "name": v.name, "visual": v.visual_type}
            for v in row_visuals
        ]
        rows.append({
            "id": f"row{row_idx}",
            "height": math.ceil(row_hts[row_idx]),
            "cols": cols,
        })

    return rows


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_layout(data: dict) -> None:
    """Print a height-budget report and auto-fit canvas.height to the tallest page."""
    canvas_height: int = data.get("canvas", {}).get("height", 720)
    pages: list[dict] = data.get("pages", [])
    if not pages:
        return

    totals = {
        p.get("display_name", p["id"]): sum(r.get("height", 0) for r in p.get("rows", []))
        for p in pages
    }
    max_height = max(totals.values(), default=canvas_height)

    if max_height != canvas_height:
        data.setdefault("canvas", {})["height"] = max_height
        print(f"\n  canvas.height adjusted: {canvas_height}px → {max_height}px")
        canvas_height = max_height

    col_w = max(len(name) for name in totals)
    sep = "─" * (col_w + 36)

    print(f"\n── Layout height validation  (canvas: {canvas_height}px) ──")
    print(f"  {'Page':<{col_w}}   Total    Delta")
    print(f"  {sep}")

    issues = 0
    for name, total in totals.items():
        diff = total - canvas_height
        if diff == 0:
            marker, note = "✓", ""
        elif diff > 0:
            marker, note, issues = "▲", f"  +{diff}px  OVERFLOW", issues + 1
        else:
            marker, note, issues = "▼", f"  {diff}px  underflow", issues + 1
        print(f"  {marker} {name:<{col_w}}  {total:>4}px{note}")

    print(f"  {sep}")
    if issues == 0:
        print("  All pages fit the canvas.")
    else:
        print(f"  {issues} page(s) with height mismatch — adjust row heights before running generate.")

    _validate_spans(data)


def _validate_spans(data: dict) -> None:
    """Warn when any row's explicit span sum exceeds 12 columns.

    Note: rowspan carry from menu/sidebar columns is NOT counted here —
    actual overflow at render time may be larger than reported.
    """
    issues: list[str] = []
    for page in data.get("pages", []):
        page_name = page.get("display_name", page["id"])
        for row in page.get("rows", []):
            total = sum(c.get("span", 0) for c in row.get("cols", []) if "span" in c)
            if total > 12:
                issues.append(
                    f"  ▲ page '{page_name}' / row '{row.get('id', '?')}': span sum = {total} > 12"
                )

    if issues:
        print(f"\n── Column span validation ──")
        for msg in issues:
            print(msg)
        print(f"  {len(issues)} row(s) with column overflow — fix spans before running generate.")
        print(f"  Note: rowspan carry from menu/sidebar is NOT counted; actual overflow may be larger.")


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
    import os

    report = Report.from_pbir(report_path)

    # Round-trip merge: preserve the user's comments/formatting in the existing
    # YAML. PyYAML drops comments on load, so we use ruamel only when merging.
    round_trip = bool(merge_with and merge_with.exists())
    if round_trip:
        ryaml = _ruamel()
        top = ryaml.load(merge_with.read_text(encoding="utf-8")) or {}
    else:
        ryaml = None
        top = {}
    existing_pages = {page["id"]: page for page in top.get("pages", [])}

    pages_data: list[Any] = []
    for page in report.pages:
        if page.name in existing_pages:
            # mutate the existing (commented) page object in place — keeps comments
            pages_data.append(_merge_page(page, existing_pages[page.name]))
        else:
            rows = _infer_page_rows(page.visuals, page.width, page.height)
            pages_data.append({
                "id": page.name,
                "display_name": page.display_name,
                "rows": rows,
            })

    if output is None:
        output = merge_with if merge_with else report_path.parent / f"{report.name}_layout.yaml"

    source_rel = os.path.relpath(report_path.resolve(), output.parent.resolve())

    # Update the managed keys in place so non-managed top-level keys (and their
    # comments) survive untouched.
    report_block = top.get("report")
    if report_block is None:
        report_block = {"name": report.name}
        top["report"] = report_block
    report_block["source"] = source_rel
    if "canvas" not in top:
        top["canvas"] = {
            "width": report.pages[0].width if report.pages else 1280,
            "height": report.pages[0].height if report.pages else 720,
            "gutter": 4,
        }
    top["pages"] = pages_data

    validate_layout(top)
    output.parent.mkdir(parents=True, exist_ok=True)
    if round_trip:
        from io import StringIO
        buf = StringIO()
        ryaml.dump(top, buf)
        output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        output.write_text(
            yaml.dump(top, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
    return output


def _ruamel():
    """A ruamel YAML configured to match the project's dash-at-parent list style."""
    from ruamel.yaml import YAML
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096                              # avoid line wrapping of long strings
    y.indent(mapping=2, sequence=2, offset=0)   # `key:` then `- item` at same indent
    return y


def _merge_page(page, existing: dict[str, Any]) -> dict[str, Any]:
    """Append rows for newly-added visuals, mutating *existing* in place.

    Mutating in place (rather than rebuilding the dict) preserves comments when
    *existing* is a ruamel ``CommentedMap``.

    A visual is "already referenced" if it appears either as a column ``name`` or
    inside any column's ``overlay`` list — otherwise an overlaid visual (e.g. a
    total card over a donut) would be re-added as a standalone col on every merge.
    """
    referenced: set[str] = set()
    for row in existing.get("rows", []):
        for col in row.get("cols", []):
            if col.get("name"):
                referenced.add(col["name"])
            for ov in col.get("overlay") or []:
                if ov.get("name"):
                    referenced.add(ov["name"])
    new_visuals = [v for v in page.visuals if v.name not in referenced]
    if not new_visuals:
        return existing

    new_rows = _infer_page_rows(new_visuals, page.width, page.height)
    existing_row_ids = {r["id"] for r in existing.get("rows", [])}
    for row in new_rows:
        base, n = row["id"], 0
        while row["id"] in existing_row_ids:
            n += 1
            row["id"] = f"{base}_{n}"
        existing_row_ids.add(row["id"])

    rows = existing.get("rows")
    if rows is None:
        existing["rows"] = new_rows
    else:
        rows.extend(new_rows)
    return existing
