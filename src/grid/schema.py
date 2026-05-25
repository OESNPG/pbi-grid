from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── Grid geometry ──────────────────────────────────────────────────────────────

@dataclass
class Canvas:
    width: int = 1280
    height: int = 720
    gutter: float = 4.0


@dataclass
class Cell:
    """Resolved grid cell — output of the engine, input to components."""
    x: float
    y: float
    width: float
    height: float
    z: int


# ── Layout specification (parsed from YAML) ────────────────────────────────────

@dataclass
class ColSpec:
    span: int
    name: str | None = None       # PBIR visual name — references an existing visual by identity
    component: str | None = None
    visual: str | None = None     # Power BI visual type (used when creating new bare visuals)
    rowspan: int = 1
    height: float | None = None   # override visual height within the row (default: full row height)
    valign: str = "top"           # vertical alignment: top | center | bottom
    border: bool = False          # render a border shape behind this cell
    border_color: str | None = None
    border_weight: float | None = None
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class RowSpec:
    id: str
    height: int
    cols: list[ColSpec]
    border: bool = False
    border_color: str | None = None
    border_weight: float | None = None


@dataclass
class SharedRowSpec:
    """Cols to prepend into a named row across every page.

    When a page has a row whose id matches shared_row.id, the shared cols are
    inserted before that page's own cols. Pages that lack the matching row id
    receive a new row at the top with these cols (using the fallback height).
    """
    id: str
    cols: list[ColSpec]
    height: int = 0  # fallback height when page has no matching row


@dataclass
class PageSpec:
    id: str
    display_name: str
    rows: list[RowSpec]


# ── YAML parsing helpers ───────────────────────────────────────────────────────

_KNOWN_COL_KEYS = {
    "span", "name", "component", "visual", "rowspan", "ref",
    "height", "valign", "border", "border_color", "border_weight",
}


def _resolve_ref(col_raw: dict[str, Any], shared_components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Merge a shared component definition with local col overrides.

    Returns the merged dict; raises ValueError when the ref name is unknown.
    """
    ref = col_raw.get("ref")
    if not ref:
        return col_raw
    if ref not in shared_components:
        raise ValueError(
            f"ref '{ref}' not found in shared.components. "
            f"Available: {list(shared_components)}"
        )
    base = dict(shared_components[ref])
    base.update({k: v for k, v in col_raw.items() if k != "ref"})
    return base


def _make_colspec(col_raw: dict[str, Any], shared_components: dict[str, dict[str, Any]]) -> ColSpec:
    """Parse one col dict (after ref resolution) into a ColSpec."""
    col_raw = _resolve_ref(col_raw, shared_components)
    raw_h = col_raw.get("height")
    raw_bw = col_raw.get("border_weight")
    return ColSpec(
        span=col_raw.get("span", 12),
        name=col_raw.get("name"),
        component=col_raw.get("component"),
        visual=col_raw.get("visual"),
        rowspan=col_raw.get("rowspan", 1),
        height=float(raw_h) if raw_h is not None else None,
        valign=col_raw.get("valign", "top"),
        border=bool(col_raw.get("border", False)),
        border_color=col_raw.get("border_color") or None,
        border_weight=float(raw_bw) if raw_bw is not None else None,
        props={k: v for k, v in col_raw.items() if k not in _KNOWN_COL_KEYS},
    )


def _parse_rows(rows_raw: list[dict], shared_components: dict[str, dict[str, Any]]) -> list[RowSpec]:
    """Parse a list of row dicts into RowSpec objects."""
    rows: list[RowSpec] = []
    for row_raw in rows_raw:
        cols = [_make_colspec(c, shared_components) for c in row_raw.get("cols", [])]
        raw_bw = row_raw.get("border_weight")
        rows.append(RowSpec(
            id=row_raw["id"],
            height=row_raw.get("height", 0),
            cols=cols,
            border=bool(row_raw.get("border", False)),
            border_color=row_raw.get("border_color") or None,
            border_weight=float(raw_bw) if raw_bw is not None else None,
        ))
    return rows


# ── LayoutSpec ─────────────────────────────────────────────────────────────────

@dataclass
class LayoutSpec:
    report_name: str
    package: str | None
    canvas: Canvas
    pages: list[PageSpec]
    shared_rows: list[SharedRowSpec] = field(default_factory=list)
    source_path: Path | None = None          # layout YAML path
    source_report_path: Path | None = None   # existing .Report to pull visual data from

    @classmethod
    def from_yaml(cls, path: Path) -> "LayoutSpec":
        """Parse a layout YAML file into a LayoutSpec.

        Resolves all ``ref:`` references against ``shared.components`` at parse
        time so the engine never needs to look them up again.
        """
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        canvas_raw = data.get("canvas", {})
        canvas = Canvas(
            width=canvas_raw.get("width", 1280),
            height=canvas_raw.get("height", 720),
            gutter=canvas_raw.get("gutter", 0.0),
        )

        shared_components: dict[str, dict[str, Any]] = {
            name: comp
            for name, comp in data.get("shared", {}).get("components", {}).items()
        }

        shared_rows: list[SharedRowSpec] = [
            SharedRowSpec(
                id=row_raw["id"],
                cols=[_make_colspec(c, shared_components) for c in row_raw.get("cols", [])],
                height=row_raw.get("height", 0),
            )
            for row_raw in data.get("shared", {}).get("rows", [])
        ]

        pages: list[PageSpec] = [
            PageSpec(
                id=page_raw["id"],
                display_name=page_raw.get("display_name", page_raw["id"]),
                rows=_parse_rows(page_raw.get("rows", []), shared_components),
            )
            for page_raw in data.get("pages", [])
        ]

        report_raw = data.get("report", {})
        source_report_path: Path | None = None
        if source_raw := report_raw.get("source"):
            source_report_path = (path.parent / source_raw).resolve()

        return cls(
            report_name=report_raw.get("name", path.stem),
            package=data.get("package"),
            canvas=canvas,
            pages=pages,
            shared_rows=shared_rows,
            source_path=path,
            source_report_path=source_report_path,
        )
