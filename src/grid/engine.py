import hashlib

from .schema import LayoutSpec, PageSpec, RowSpec, ColSpec, Canvas, Cell, SharedRowSpec
from ..models import Position, Visual, Page, Report

_DEBUG_FILL = "#4169E1"       # royal blue semi-transparent fill
_DEBUG_OUTLINE = "#FF6600"    # orange border
_DEBUG_TEXT = "#FF6600"       # orange label text

_GRID_COLUMNS = 12
_Z_STEP = 1000
_Z_COMPONENT_SUBSTEP = 100  # sub-step for visuals within the same component


def _make_id(seed: str) -> str:
    """Deterministic 20-char hex ID matching Power BI's naming convention.

    If seed is already a 20-char lowercase hex string (real PBIR ID), pass it through.
    """
    if len(seed) == 20 and all(c in "0123456789abcdef" for c in seed):
        return seed
    return hashlib.md5(seed.encode()).hexdigest()[:20]


def _literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _hex_color(hex_value: str) -> dict:
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_value}'"}}}}}


def _debug_cell_visual(cell: Cell, label: str, z_top: int) -> list[Visual]:
    """Two visuals: a semi-transparent fill rectangle + an actionButton label."""
    vid_rect = _make_id(f"dbg-rect-{cell.z}-{label}")
    rect = Visual(
        name=vid_rect,
        visual_type="shape",
        position=Position(
            x=cell.x, y=cell.y, z=z_top,
            width=cell.width, height=cell.height,
            tab_order=z_top,
        ),
        config={
            "objects": {
                "fill": [
                    {"properties": {
                        "show": _literal("true"),
                        "fillColor": _hex_color(_DEBUG_FILL),
                        "transparency": _literal("80D"),
                    }},
                    {
                        "properties": {"fillColor": _hex_color(_DEBUG_FILL)},
                        "selector": {"id": "default"},
                    },
                ],
                "outline": [
                    {"properties": {"show": _literal("false")}},
                    {
                        "properties": {
                            "lineColor": _hex_color(_DEBUG_OUTLINE),
                            "weight": _literal("2D"),
                            "show": _literal("true"),
                        },
                        "selector": {"id": "default"},
                    },
                ],
                "shape": [{"properties": {"tileShape": _literal("'rectangle'")}}],
                "rotation": [{"properties": {"shapeAngle": _literal("0L")}}],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": _literal("false")}}],
            },
        },
    )

    vid_lbl = _make_id(f"dbg-lbl-{cell.z}-{label}")
    lbl = Visual(
        name=vid_lbl,
        visual_type="actionButton",
        position=Position(
            x=cell.x, y=cell.y, z=z_top + 1,
            width=cell.width, height=min(cell.height, 24.0),
            tab_order=z_top + 1,
        ),
        config={
            "objects": {
                "icon": [{"properties": {"show": _literal("false")}}],
                "outline": [{"properties": {"show": _literal("false")}}],
                "fill": [{"properties": {"show": _literal("false")}}],
                "text": [
                    {"properties": {"show": _literal("true")}},
                    {
                        "properties": {
                            "text": _literal(f"'{label}'"),
                            "fontColor": _hex_color(_DEBUG_TEXT),
                            "verticalAlignment": _literal("'top'"),
                            "horizontalAlignment": _literal("'left'"),
                            "fontSize": _literal("8D"),
                            "fontFamily": _literal("'Segoe UI', wf_standard-font, helvetica, arial, sans-serif"),
                            "leftMargin": _literal("4L"),
                            "bold": _literal("true"),
                        },
                        "selector": {"id": "default"},
                    },
                ],
            },
            "visualContainerObjects": {
                "visualLink": [{"properties": {"show": _literal("false")}}],
                "visualHeader": [{"properties": {"show": _literal("false")}}],
                "background": [{"properties": {"show": _literal("false")}}],
                "border": [{"properties": {"show": _literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        },
    )
    return [rect, lbl]


def _rowspan_height(rows: list[RowSpec], row_idx: int, rowspan: int) -> float:
    end = min(row_idx + rowspan, len(rows))
    return sum(rows[i].height for i in range(row_idx, end))


def _apply_shared(page_spec: PageSpec, shared_rows: list[SharedRowSpec]) -> PageSpec:
    """Prepend shared cols into matching page rows; insert missing shared rows at the top."""
    if not shared_rows:
        return page_spec

    page_row_map = {r.id: r for r in page_spec.rows}
    new_rows: list[RowSpec] = []

    for sr in shared_rows:
        if sr.id in page_row_map:
            pr = page_row_map[sr.id]
            new_rows.append(RowSpec(id=pr.id, height=pr.height, cols=sr.cols + pr.cols))
        else:
            new_rows.append(RowSpec(id=sr.id, height=sr.height, cols=sr.cols))

    shared_ids = {sr.id for sr in shared_rows}
    for pr in page_spec.rows:
        if pr.id not in shared_ids:
            new_rows.append(pr)

    return PageSpec(id=page_spec.id, display_name=page_spec.display_name, rows=new_rows)


def _build_page(
    page_spec: PageSpec,
    canvas: Canvas,
    page_id_map: dict[str, str],
    source_visuals: dict[str, Visual] | None = None,
    source_pages: dict[str, "Page"] | None = None,
    tokens: dict | None = None,
    debug: bool = False,
    theme_dir=None,
) -> Page:
    from ..components import resolve_component

    page_name = page_id_map[page_spec.display_name]
    src_page = source_pages.get(page_name) if source_pages else None

    page = Page(
        name=page_name,
        display_name=page_spec.display_name,
        width=canvas.width,
        height=canvas.height,
        raw_page_data=src_page.raw_page_data if src_page else None,
    )

    col_unit = canvas.width / _GRID_COLUMNS
    g = canvas.gutter / 2
    z = _Z_STEP

    # Track x_offset already reserved in future rows by rowspan > 1 columns.
    rowspan_carry: dict[int, float] = {}

    y_offset = 0.0
    for row_idx, row in enumerate(page_spec.rows):
        x_offset = rowspan_carry.get(row_idx, 0.0)
        for col in row.cols:
            raw_w = col_unit * col.span
            raw_h = _rowspan_height(page_spec.rows, row_idx, col.rowspan)

            cell = Cell(
                x=round(x_offset + g, 4),
                y=round(y_offset + g, 4),
                width=round(raw_w - 2 * g, 4),
                height=round(raw_h - 2 * g, 4),
                z=z,
            )

            if col.component:
                component = resolve_component(col.component, col.props, page_id_map, tokens, theme_dir=theme_dir)
                visuals = component.resolve(cell)
            elif col.name:
                # Named visual — references an existing visual by its PBIR identity.
                src = source_visuals.get(col.name) if source_visuals else None
                visuals = [Visual(
                    name=col.name,
                    visual_type=src.visual_type if src else (col.visual or "textbox"),
                    position=Position(
                        x=cell.x, y=cell.y, z=cell.z,
                        width=cell.width, height=cell.height,
                        tab_order=cell.z,
                    ),
                    raw_data=src.raw_data if src else None,
                )]
            else:
                vid = _make_id(f"{page_spec.id}-{row.id}-{col.visual or 'empty'}-{z}")
                visuals = [Visual(
                    name=vid,
                    visual_type=col.visual or "textbox",
                    position=Position(
                        x=cell.x, y=cell.y, z=cell.z,
                        width=cell.width, height=cell.height,
                        tab_order=cell.z,
                    ),
                )]

            for visual in visuals:
                page.add_visual(visual)

            if debug:
                kind = col.component or col.name or col.visual or "cell"
                span_info = f"{kind} {col.span}c"
                if col.rowspan > 1:
                    span_info += f"×{col.rowspan}r"
                z_top = z + _Z_STEP - 10
                for dv in _debug_cell_visual(cell, span_info, z_top):
                    page.add_visual(dv)

            if col.rowspan > 1:
                for future in range(row_idx + 1, row_idx + col.rowspan):
                    rowspan_carry[future] = rowspan_carry.get(future, 0.0) + raw_w

            z += _Z_STEP
            x_offset += raw_w

        y_offset += row.height

    return page


def build(layout: LayoutSpec, debug: bool = False) -> Report:
    from ..packages import load_tokens, theme_dir as get_theme_dir
    tokens = load_tokens(layout.package)
    pkg_theme_dir = get_theme_dir(layout.package)

    # Pre-generate all page IDs so the menu component can resolve them
    # before any page is actually built.
    page_id_map: dict[str, str] = {
        spec.display_name: _make_id(spec.id)
        for spec in layout.pages
    }

    # Load source report to preserve visual data and report/page-level metadata.
    source_visuals: dict[str, Visual] | None = None
    source_pages: dict[str, Page] | None = None
    raw_report_data: dict | None = None
    dataset_reference: dict | None = None
    if layout.source_report_path and layout.source_report_path.exists():
        from ..models import Report as _Report
        src_report = _Report.from_pbir(layout.source_report_path)
        source_visuals = {v.name: v for page in src_report.pages for v in page.visuals}
        source_pages = {p.name: p for p in src_report.pages}
        raw_report_data = src_report.raw_report_data
        dataset_reference = src_report.dataset_reference

    report = Report(
        name=layout.report_name,
        raw_report_data=raw_report_data,
        dataset_reference=dataset_reference,
        active_page_name=src_report.active_page_name if source_pages else None,
    )
    for page_spec in layout.pages:
        merged = _apply_shared(page_spec, layout.shared_rows)
        page = _build_page(merged, layout.canvas, page_id_map, source_visuals, source_pages, tokens, debug=debug, theme_dir=pkg_theme_dir)
        report.add_page(page)

    # Register static resources (footer logos from tokens + layout prop overrides)
    if pkg_theme_dir:
        from pathlib import Path as _Path
        seen: set[str] = set()
        logo_candidates: list[str] = []
        token_logo = tokens.get("footer", {}).get("logo_path")
        if token_logo:
            logo_candidates.append(token_logo)
        for page in layout.pages:
            for row in page.rows:
                for col in row.cols:
                    if col.component == "footer":
                        lp = col.props.get("logo_path", "")
                        if lp:
                            logo_candidates.append(lp)
        for sr in layout.shared_rows:
            for col in sr.cols:
                if col.component == "footer":
                    lp = col.props.get("logo_path", "")
                    if lp:
                        logo_candidates.append(lp)
        for logo_rel in logo_candidates:
            item_name = _Path(logo_rel).name
            if item_name in seen:
                continue
            logo_full = pkg_theme_dir / logo_rel
            if logo_full.exists():
                report.registered_resources.append((item_name, logo_full))
                seen.add(item_name)

    return report
