from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── Grid geometry ──────────────────────────────────────────────────────────────

@dataclass
class Canvas:
    width: int = 1280
    height: int = 720
    gutter: float = 0.0


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
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class RowSpec:
    id: str
    height: int
    cols: list[ColSpec]


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
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        canvas_raw = data.get("canvas", {})
        canvas = Canvas(
            width=canvas_raw.get("width", 1280),
            height=canvas_raw.get("height", 720),
            gutter=canvas_raw.get("gutter", 0.0),
        )

        # Parse named shared components — resolved at parse time when `ref:` is used.
        _known_col = {"span", "name", "component", "visual", "rowspan", "ref"}
        shared_components: dict[str, dict[str, Any]] = {
            name: comp
            for name, comp in data.get("shared", {}).get("components", {}).items()
        }

        def _make_colspec(col_raw: dict[str, Any]) -> ColSpec:
            # Resolve ref: merge shared component defaults with local overrides.
            ref = col_raw.get("ref")
            if ref:
                if ref not in shared_components:
                    raise ValueError(
                        f"ref '{ref}' not found in shared.components. "
                        f"Available: {list(shared_components)}"
                    )
                base = dict(shared_components[ref])
                base.update({k: v for k, v in col_raw.items() if k != "ref"})
                col_raw = base
            return ColSpec(
                span=col_raw.get("span", 12),
                name=col_raw.get("name"),
                component=col_raw.get("component"),
                visual=col_raw.get("visual"),
                rowspan=col_raw.get("rowspan", 1),
                props={k: v for k, v in col_raw.items() if k not in _known_col},
            )

        def _parse_cols(rows_raw: list[dict]) -> list[RowSpec]:
            rows: list[RowSpec] = []
            for row_raw in rows_raw:
                cols = [_make_colspec(c) for c in row_raw.get("cols", [])]
                rows.append(RowSpec(
                    id=row_raw["id"],
                    height=row_raw.get("height", 0),
                    cols=cols,
                ))
            return rows

        shared_rows: list[SharedRowSpec] = []
        for row_raw in data.get("shared", {}).get("rows", []):
            cols = [_make_colspec(c) for c in row_raw.get("cols", [])]
            shared_rows.append(SharedRowSpec(
                id=row_raw["id"],
                cols=cols,
                height=row_raw.get("height", 0),
            ))

        pages: list[PageSpec] = []
        for page_raw in data.get("pages", []):
            rows = _parse_cols(page_raw.get("rows", []))
            pages.append(PageSpec(
                id=page_raw["id"],
                display_name=page_raw.get("display_name", page_raw["id"]),
                rows=rows,
            ))

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
