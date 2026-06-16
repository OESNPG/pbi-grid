import copy

from .schema import LayoutSpec, PageSpec, RowSpec, ColSpec, Canvas, Cell, SharedRowSpec, OverlaySpec
from ..models import Position, Visual, Page, Report
from ..pbir_utils import make_id, literal, hex_color

_DEBUG_FILL = "#4169E1"
_DEBUG_OUTLINE = "#FF6600"
_DEBUG_TEXT = "#FF6600"

_GRID_COLUMNS = 12
_Z_STEP = 1000


# ── Debug overlay ───────────────────────────────────────────────────────────────

def _debug_cell_visual(cell: Cell, label: str, z_top: int) -> list[Visual]:
    """Two visuals: a semi-transparent fill rectangle and an orange label button."""
    rect = Visual(
        name=make_id(f"dbg-rect-{cell.z}-{label}"),
        visual_type="shape",
        position=Position(x=cell.x, y=cell.y, z=z_top, width=cell.width, height=cell.height, tab_order=z_top),
        config={
            "objects": {
                "fill": [
                    {"properties": {
                        "show": literal("true"),
                        "fillColor": hex_color(_DEBUG_FILL),
                        "transparency": literal("80D"),
                    }},
                    {"properties": {"fillColor": hex_color(_DEBUG_FILL)}, "selector": {"id": "default"}},
                ],
                "outline": [
                    {"properties": {"show": literal("false")}},
                    {"properties": {
                        "lineColor": hex_color(_DEBUG_OUTLINE),
                        "weight": literal("2D"),
                        "show": literal("true"),
                    }, "selector": {"id": "default"}},
                ],
                "shape": [{"properties": {"tileShape": literal("'rectangle'")}}],
                "rotation": [{"properties": {"shapeAngle": literal("0L")}}],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": literal("false")}}],
            },
        },
    )
    lbl = Visual(
        name=make_id(f"dbg-lbl-{cell.z}-{label}"),
        visual_type="actionButton",
        position=Position(
            x=cell.x, y=cell.y, z=z_top + 1,
            width=cell.width, height=min(cell.height, 24.0), tab_order=z_top + 1,
        ),
        config={
            "objects": {
                "icon": [{"properties": {"show": literal("false")}}],
                "outline": [{"properties": {"show": literal("false")}}],
                "fill": [{"properties": {"show": literal("false")}}],
                "text": [
                    {"properties": {"show": literal("true")}},
                    {"properties": {
                        "text": literal(f"'{label}'"),
                        "fontColor": hex_color(_DEBUG_TEXT),
                        "verticalAlignment": literal("'top'"),
                        "horizontalAlignment": literal("'left'"),
                        "fontSize": literal("8D"),
                        "fontFamily": literal("'Segoe UI', wf_standard-font, helvetica, arial, sans-serif"),
                        "leftMargin": literal("4L"),
                        "bold": literal("true"),
                    }, "selector": {"id": "default"}},
                ],
            },
            "visualContainerObjects": {
                "visualLink": [{"properties": {"show": literal("false")}}],
                "visualHeader": [{"properties": {"show": literal("false")}}],
                "background": [{"properties": {"show": literal("false")}}],
                "border": [{"properties": {"show": literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        },
    )
    return [rect, lbl]


# ── Grid helpers ────────────────────────────────────────────────────────────────

def _rowspan_height(rows: list[RowSpec], row_idx: int, rowspan: int) -> float:
    """Sum of row heights from row_idx up to (but not exceeding) rowspan rows."""
    end = min(row_idx + rowspan, len(rows))
    return sum(rows[i].height for i in range(row_idx, end))


def _find_next_x(x_start: float, width: float, blocked: list[tuple[float, float]]) -> float:
    """Find leftmost x >= x_start where *width* fits without overlapping any blocked interval.

    Iterates until no remaining block overlaps [x, x+width). Handles arbitrary
    interval ordering and chains of adjacent blocked ranges.
    """
    x = x_start
    moved = True
    while moved:
        moved = False
        for bx, bw in blocked:
            if x < bx + bw and x + width > bx:
                x = bx + bw
                moved = True
    return x


# ── Border / divider shapes ─────────────────────────────────────────────────────

def _border_color(tokens: dict, override: str | None) -> str:
    """Resolve border color from token override or theme default."""
    return override or tokens.get("layout", {}).get("border_color") or "#E0E0E0"


def _border_weight(tokens: dict, override: float | None) -> float:
    """Resolve border weight from token override or theme default."""
    raw = tokens.get("layout", {}).get("border_weight", 1)
    return override if override is not None else float(raw)


def _border_radius(tokens: dict) -> int:
    """Resolve corner radius (px) from theme tokens."""
    return int(tokens.get("layout", {}).get("border_radius", 0))


def _make_border_shape(cell: Cell, color: str, weight: float, radius: int = 0) -> Visual:
    """Transparent rectangle with a visible outline — used for card/panel borders."""
    shape_props: dict = {"tileShape": literal("'rectangle'")}
    if radius > 0:
        shape_props["roundEdge"] = {"expr": {"Literal": {"Value": f"{radius}L"}}}
    vid = make_id(f"border-{cell.x:.0f}-{cell.y:.0f}-{cell.z}")
    return Visual(
        name=vid,
        visual_type="shape",
        position=Position(
            x=cell.x, y=cell.y, z=cell.z - 1,
            width=cell.width, height=cell.height, tab_order=cell.z - 1,
        ),
        config={
            "objects": {
                "fill": [{"properties": {"show": literal("false")}}],
                "shape": [{"properties": shape_props}],
                "rotation": [{"properties": {"shapeAngle": literal("0L")}}],
                "outline": [
                    {"properties": {"show": literal("true")}},
                    {"properties": {
                        "show": literal("true"),
                        "lineColor": hex_color(color),
                        "weight": literal(f"{int(weight)}D"),
                    }, "selector": {"id": "default"}},
                ],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": literal("false")}}],
            },
        },
    )


def _make_divider_shape(x: float, y: float, width: float, height: float, z: int, color: str) -> Visual:
    """Solid filled rectangle used as a vertical menu divider stripe."""
    return Visual(
        name=make_id(f"menu-div-{x:.0f}-{y:.0f}-{z}"),
        visual_type="shape",
        position=Position(x=x, y=y, z=z, width=width, height=height, tab_order=z),
        config={
            "objects": {
                "fill": [
                    {"properties": {
                        "show": literal("true"),
                        "fillColor": hex_color(color),
                        "transparency": literal("0D"),
                    }},
                    {"properties": {"fillColor": hex_color(color)}, "selector": {"id": "default"}},
                ],
                "shape": [{"properties": {"tileShape": literal("'rectangle'")}}],
                "rotation": [{"properties": {"shapeAngle": literal("0L")}}],
                "outline": [{"properties": {"show": literal("false")}}],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": literal("false")}}],
            },
        },
    )


# ── Shared-row injection ────────────────────────────────────────────────────────

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

    return PageSpec(id=page_spec.id, display_name=page_spec.display_name, rows=new_rows, canvas=page_spec.canvas)


# ── Column rendering ────────────────────────────────────────────────────────────

def _render_col(
    col: ColSpec,
    cell: Cell,
    x_offset: float,
    y_offset: float,
    raw_w: float,
    raw_h: float,
    row: RowSpec,
    page_spec: PageSpec,
    page_id_map: dict[str, str],
    source_visuals: dict[str, Visual] | None,
    tokens: dict,
    theme_dir,
    z: int,
) -> list[Visual]:
    """Translate one ColSpec into its PBIR visuals (component, named, or placeholder).

    Any ``col.overlay`` visuals are appended on top of the cell (higher z).
    """
    from ..components import resolve_component

    if col.component:
        component = resolve_component(col.component, col.props, page_id_map, tokens, theme_dir=theme_dir)
        visuals = component.resolve(cell)
        if col.component == "menu" and col.props.get("orientation", "vertical") == "vertical":
            div_color = tokens.get("menu", {}).get("divider_color")
            div_weight = float(tokens.get("menu", {}).get("divider_weight", 1))
            if div_color:
                visuals.append(_make_divider_shape(
                    x=round(x_offset + raw_w - div_weight, 4),
                    y=round(y_offset, 4),
                    width=div_weight,
                    height=round(raw_h, 4),
                    z=z - 1,
                    color=div_color,
                ))
    elif col.name:
        src = source_visuals.get(col.name) if source_visuals else None
        vtype = src.visual_type if src else (col.visual or "textbox")
        raw = src.raw_data if src else None
        if raw is not None and vtype == "textbox":
            raw = _normalize_textbox_font(raw, tokens)
        visuals = [Visual(
            name=col.name,
            visual_type=vtype,
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height, tab_order=cell.z,
            ),
            raw_data=raw,
        )]
    else:
        vid = make_id(f"{page_spec.id}-{row.id}-{col.visual or 'empty'}-{z}")
        visuals = [Visual(
            name=vid,
            visual_type=col.visual or "textbox",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height, tab_order=cell.z,
            ),
        )]

    if col.config and not col.component and visuals:
        if col.config.title:
            _apply_title(visuals[0], col.config.title, visuals[0].visual_type)   # header title (or card label)
        if col.name:
            # ⓘ trigger card → hidden tooltip page with the component's info modal
            visuals.append(_make_info_icon_card(cell, col.name, cell.z + 700, tokens, visuals[0].visual_type))

    for i, ov in enumerate(col.overlay):
        visuals.extend(_render_overlay(ov, cell, source_visuals, tokens, cell.z + 500 + i))
    return visuals


def _text_literal(text: str) -> str:
    """PBIR string literal ('...' with single quotes doubled)."""
    return "'" + text.replace("'", "''") + "'"


def _apply_title(visual: Visual, text: str, vtype: str | None = None) -> None:
    """Set the component's visible title from config, mutating the visual.

    For most visuals this is the header title (visualContainerObjects.title). A
    cardVisual, however, shows the field's *display name* as its label (not the
    header title), so there we override the query projection's ``displayName``
    instead — the equivalent of renaming the field on the visual.
    """
    if vtype == "cardVisual" and visual.raw_data is not None:
        raw = copy.deepcopy(visual.raw_data)
        roles = raw.get("visual", {}).get("query", {}).get("queryState", {})
        for role in roles.values():
            for proj in role.get("projections", []):
                proj["displayName"] = text
        visual.raw_data = raw
        return
    lit = {"expr": {"Literal": {"Value": _text_literal(text)}}}
    if visual.raw_data is not None:
        raw = copy.deepcopy(visual.raw_data)
        vco = raw.setdefault("visual", {}).setdefault("visualContainerObjects", {})
    else:
        vco = visual.config.setdefault("visualContainerObjects", {})
        raw = None
    titles = vco.setdefault("title", [{"properties": {}}])
    titles[0].setdefault("properties", {})["text"] = lit
    if raw is not None:
        visual.raw_data = raw


_PAGE_SCHEMA_2_1 = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"


def _make_info_icon_card(cell: Cell, name: str, z: int, tokens: dict, vtype: str | None = None) -> Visual:
    """Small ⓘ card (data visual) at the cell's top-right, carrying a report-page
    tooltip to the component's hidden info page. A data visual is required because
    buttons/images/shapes don't fire report-page tooltips. Styled clean/transparent.
    """
    from .info_table import TABLE_NAME, ICON_MEASURE, info_page_id, info_icon_id

    cfg = (tokens.get("info_icon", {}) if tokens else {}) or {}
    size = float(cfg.get("size", 28))
    font_size = cfg.get("font_size", 10)
    margin = float(cfg.get("margin", 2))
    page_id = info_page_id(name)
    _TABLE_TYPES = {"tableEx", "pivotTable"}
    if vtype == "cardVisual":
        # KPI cards: vertically centered on the right (clears the value/accent bar)
        card_margin = float(cfg.get("card_margin", 16))
        card_v_offset = float(cfg.get("card_v_offset", -8))   # 8px above the vertical center
        x = round(cell.x + cell.width - size - card_margin, 4)
        y = round(cell.y + (cell.height - size) / 2 + card_v_offset, 4)
    elif vtype in _TABLE_TYPES:
        # tables: top-right corner
        x = round(cell.x + cell.width - size - margin, 4)
        y = round(cell.y + margin, 4)
    else:
        # charts/maps: nudged down so it clears the chart title
        chart_top = float(cfg.get("chart_top_margin", 16))
        x = round(cell.x + cell.width - size - margin, 4)
        y = round(cell.y + chart_top, 4)
    return Visual(
        name=info_icon_id(name),
        visual_type="cardVisual",
        position=Position(x=x, y=y, z=z, width=size, height=size, tab_order=z),
        config={
            "query": {"queryState": {"Data": {"projections": [{
                "field": {"Measure": {"Expression": {"SourceRef": {"Entity": TABLE_NAME}}, "Property": ICON_MEASURE}},
                "queryRef": f"{TABLE_NAME}.{ICON_MEASURE}",
                "nativeQueryRef": ICON_MEASURE,
            }]}}},
            "objects": {
                # label off (hides the measure name "icon"); chrome stripped like the
                # donut total cards so the glyph isn't clipped in a small card.
                "label": [{"properties": {"show": literal("false")}, "selector": {"id": "default"}}],
                "value": [{"properties": {
                    "fontSize": literal(f"{font_size}D"),
                    "transparency": literal("0D"),
                    "horizontalAlignment": literal("'center'"),
                }, "selector": {"id": "default"}}],
                "cardCalloutArea": [{"properties": {
                    "show": literal("false"),
                    "backgroundTransparency": literal("100D"),
                }, "selector": {"id": "default"}}],
                "outline": [{"properties": {"show": literal("false")}, "selector": {"id": "default"}}],
                "divider": [{"properties": {"show": literal("false")}, "selector": {"id": "default"}}],
                "fillCustom": [{"properties": {"show": literal("false")}}],
                "layout": [{"properties": {"backgroundShow": literal("false"), "paddingUniform": literal("0L")}, "selector": {"id": "default"}}],
                # zero inner padding so the glyph isn't swallowed in a small card
                # (Power BI appears to clamp uniform padding to a 1L minimum)
                "padding": [{"properties": {"paddingUniform": literal("0L")}, "selector": {"id": "default"}}],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": literal("false")}}],
                "padding": [{"properties": {
                    "top": literal("0D"), "bottom": literal("0D"),
                    "left": literal("0D"), "right": literal("0D"),
                }}],
                "background": [{"properties": {
                    "show": literal("false"),
                    "transparency": literal("100D"),
                }}],
                "visualTooltip": [{"properties": {
                    "show": literal("true"),
                    "section": literal(f"'{page_id}'"),
                }}],
            },
            "drillFilterOtherVisuals": True,
        },
    )


def _make_tooltip_page(name: str, tokens: dict, height: int) -> Page:
    """Hidden tooltip page rendering a component's info modal (HTML Content visual
    bound to ``pbi_grid_config[info_<name>]``)."""
    from .info_table import (
        TABLE_NAME, HTML_CONTENT_VISUAL_TYPE, info_column, info_page_id, tooltip_visual_id,
    )

    cfg = (tokens.get("info_modal", {}) if tokens else {}) or {}
    w = int(cfg.get("width", 230))
    h = int(height)
    bg = cfg.get("background", "#FFFFFF")
    page_id = info_page_id(name)
    column = info_column(name)
    html_visual = Visual(
        name=tooltip_visual_id(name),
        visual_type=HTML_CONTENT_VISUAL_TYPE,
        position=Position(x=0, y=0, z=1000, width=w, height=h, tab_order=0),
        config={
            "query": {"queryState": {"content": {"projections": [{
                "field": {"Column": {"Expression": {"SourceRef": {"Entity": TABLE_NAME}}, "Property": column}},
                "queryRef": f"{TABLE_NAME}.{column}",
                "nativeQueryRef": column,
            }]}}},
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": literal("false")}}],
                "border": [{"properties": {"show": literal("false")}}],
                "background": [{"properties": {"show": literal("false")}}],
                "dropShadow": [{"properties": {"show": literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        },
    )
    page = Page(
        name=page_id,
        display_name=f"Info {name[:8]}",
        width=w,
        height=h,
        raw_page_data={
            "$schema": _PAGE_SCHEMA_2_1,
            "name": page_id,
            "pageBinding": {"name": f"InfoTT_{name[:12]}", "type": "Default", "parameters": []},
            "objects": {
                # solid page background + outspace so the tooltip has no grey frame/border
                "background": [{"properties": {
                    "color": {"solid": {"color": literal(f"'{bg}'")}},
                    "transparency": literal("0D"),
                }}],
                "outspace": [{"properties": {
                    "color": {"solid": {"color": literal(f"'{bg}'")}},
                }}],
            },
            "visibility": "HiddenInViewMode",
            "type": "Tooltip",
        },
    )
    page.visuals = [html_visual]
    return page


def _overlay_cell(parent: Cell, ov: OverlaySpec, z: int) -> Cell:
    """Cell for an overlay, sized and aligned within the parent cell."""
    w = min(ov.width if ov.width is not None else parent.width, parent.width)
    h = min(ov.height if ov.height is not None else parent.height, parent.height)
    if ov.align == "center":
        x = parent.x + (parent.width - w) / 2
    elif ov.align == "right":
        x = parent.x + parent.width - w
    else:
        x = parent.x
    if ov.valign == "center":
        y = parent.y + (parent.height - h) / 2
    elif ov.valign == "bottom":
        y = parent.y + parent.height - h
    else:
        y = parent.y
    x += ov.offset_x
    y += ov.offset_y
    return Cell(x=round(x, 4), y=round(y, 4), width=round(w, 4), height=round(h, 4), z=z)


def _render_overlay(
    ov: OverlaySpec,
    parent: Cell,
    source_visuals: dict[str, Visual] | None,
    tokens: dict,
    z: int,
) -> list[Visual]:
    """Render one overlay visual placed on top of the parent cell."""
    cell = _overlay_cell(parent, ov, z)
    pos = Position(
        x=cell.x, y=cell.y, z=cell.z,
        width=cell.width, height=cell.height, tab_order=cell.z,
    )
    if ov.name:
        src = source_visuals.get(ov.name) if source_visuals else None
        vtype = src.visual_type if src else (ov.visual or "textbox")
        raw = src.raw_data if src else None
        if raw is not None and vtype == "textbox":
            raw = _normalize_textbox_font(raw, tokens)
        return [Visual(name=ov.name, visual_type=vtype, position=pos, raw_data=raw)]
    vid = make_id(f"overlay-{ov.visual or 'empty'}-{z}")
    return [Visual(name=vid, visual_type=ov.visual or "textbox", position=pos)]


# ── Page building ───────────────────────────────────────────────────────────────

def _normalize_textbox_font(raw_data: dict, tokens: dict) -> dict:
    """Force every textRun fontFamily of a textbox to the package font.

    Power BI ignores the theme for free text inside a textbox: each run carries an
    explicit ``fontFamily`` that overrides the theme, so a re-save in Power BI
    Desktop can silently revert it. Rewriting the runs here makes the generated
    output authoritative for the font, regardless of what the source holds.

    Controlled by the ``typography.text_font`` token; if absent, the raw data is
    returned untouched (backward compatible). The source dict is never mutated.
    """
    font = (tokens.get("typography") or {}).get("text_font")
    if not font:
        return raw_data
    raw = copy.deepcopy(raw_data)
    for gobj in raw.get("visual", {}).get("objects", {}).get("general", []):
        for para in gobj.get("properties", {}).get("paragraphs", []):
            for run in para.get("textRuns", []):
                run.setdefault("textStyle", {})["fontFamily"] = font
    return raw


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
    """Place all columns from page_spec into a Page, computing grid positions."""
    page_name = page_id_map[page_spec.display_name]
    src_page = source_pages.get(page_name) if source_pages else None
    tokens = tokens or {}

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
    # Maps future row_idx -> list of (x_start, width) blocked by rowspan columns.
    rowspan_carry: dict[int, list[tuple[float, float]]] = {}

    y_offset = 0.0
    for row_idx, row in enumerate(page_spec.rows):
        blocked = rowspan_carry.get(row_idx, [])
        x_offset = 0.0
        row_x_start: float | None = None
        row_x_end: float = 0.0
        row_first_z = z

        for col_idx, col in enumerate(row.cols):
            raw_w = col_unit * col.span
            raw_h = _rowspan_height(page_spec.rows, row_idx, col.rowspan)
            x_offset = _find_next_x(x_offset, raw_w, blocked)

            # Clamp to remaining canvas space and warn when a span overflows.
            available_w = canvas.width - x_offset
            if raw_w > available_w + 0.5:
                label = col.name or col.component or col.visual or "cell"
                print(
                    f"  WARNING: '{label}' span={col.span} overflows canvas width "
                    f"(x={x_offset:.0f} + w={raw_w:.0f} > {canvas.width}px) — clamped to {available_w:.0f}px."
                )
                raw_w = max(available_w, 0.0)

            if row_x_start is None:
                row_x_start = x_offset
            row_x_end = x_offset + raw_w

            cell_h = round(raw_h - 2 * g, 4)
            cell = Cell(
                x=round(x_offset + g, 4),
                y=round(y_offset + g, 4),
                width=round(raw_w - 2 * g, 4),
                height=cell_h,
                z=z,
            )

            if col.border:
                bc = _border_color(tokens, col.border_color)
                bw = _border_weight(tokens, col.border_weight)
                page.add_visual(_make_border_shape(cell, bc, bw, _border_radius(tokens)))

            # Apply per-column height override and vertical alignment.
            col_h = round(col.height, 4) if col.height is not None else cell_h
            if col_h != cell_h or col.valign != "top":
                dy = 0.0
                if col.valign == "center":
                    dy = (cell_h - col_h) / 2
                elif col.valign == "bottom":
                    dy = cell_h - col_h
                cell = Cell(x=cell.x, y=round(cell.y + dy, 4), width=cell.width, height=col_h, z=cell.z)

            visuals = _render_col(
                col, cell, x_offset, y_offset, raw_w, raw_h,
                row, page_spec, page_id_map,
                source_visuals, tokens, theme_dir, z,
            )
            for visual in visuals:
                page.add_visual(visual)

            if debug:
                kind = col.component or col.name or col.visual or "cell"
                short_name = kind[-5:] if len(kind) > 5 else kind
                span_info = f"name:{short_name} - pos: {row_idx} row * {col_idx} col"
                for dv in _debug_cell_visual(cell, span_info, z + _Z_STEP - 10):
                    page.add_visual(dv)

            if col.rowspan > 1:
                for future in range(row_idx + 1, row_idx + col.rowspan):
                    rowspan_carry.setdefault(future, []).append((x_offset, raw_w))

            z += _Z_STEP
            x_offset += raw_w

        if row.border and row_x_start is not None:
            bc = _border_color(tokens, row.border_color)
            bw = _border_weight(tokens, row.border_weight)
            row_border_cell = Cell(
                x=round(row_x_start + g, 4),
                y=round(y_offset + g, 4),
                width=round(row_x_end - row_x_start - 2 * g, 4),
                height=round(row.height - 2 * g, 4),
                z=row_first_z,
            )
            page.add_visual(_make_border_shape(row_border_cell, bc, bw, _border_radius(tokens)))

        y_offset += row.height

    return page


# ── Resource registration ───────────────────────────────────────────────────────

def _collect_asset_candidates(layout: LayoutSpec, tokens: dict) -> list[str]:
    """Return all relative asset paths referenced in tokens and layout col props."""
    from ..components import _collect_menu_icons

    candidates: list[str] = []

    token_footer_logo = tokens.get("footer", {}).get("logo_path")
    if token_footer_logo:
        candidates.append(token_footer_logo)
    token_header_logo = tokens.get("header", {}).get("logo_path")
    if token_header_logo:
        candidates.append(token_header_logo)

    all_cols = [
        col
        for page in layout.pages
        for row in page.rows
        for col in row.cols
    ] + [col for sr in layout.shared_rows for col in sr.cols]

    for col in all_cols:
        if col.component in ("footer", "header"):
            lp = col.props.get("logo_path", "")
            if lp:
                candidates.append(lp)
        elif col.component == "menu":
            for raw_item in col.props.get("items", []):
                _collect_menu_icons(raw_item, candidates)

    return candidates


def _register_resources(report: Report, layout: LayoutSpec, tokens: dict, theme_dir) -> None:
    """Copy referenced image assets into report.registered_resources."""
    from pathlib import Path as _Path

    seen: set[str] = set()
    for rel_path in _collect_asset_candidates(layout, tokens):
        item_name = _Path(rel_path).name
        if item_name in seen:
            continue
        full_path = theme_dir / rel_path
        if full_path.exists():
            report.registered_resources.append((item_name, full_path))
            seen.add(item_name)


# ── Public API ──────────────────────────────────────────────────────────────────

def build(layout: LayoutSpec, debug: bool = False) -> Report:
    """Compile a LayoutSpec into a fully-populated Report ready for PBIR serialization."""
    from ..packages import load_tokens, theme_dir as get_theme_dir

    tokens = load_tokens(layout.package)
    pkg_theme_dir = get_theme_dir(layout.package)

    palette_tokens = tokens.get("palette", {})
    palette_name = palette_tokens.get("name") or None
    palette_data: dict | None = _build_palette(palette_tokens) if palette_name else None

    # Pre-generate all page IDs so navigation components can resolve targets
    # before any page is actually built.
    page_id_map: dict[str, str] = {
        spec.display_name: make_id(spec.id)
        for spec in layout.pages
    }

    source_visuals, source_pages, raw_report_data, dataset_reference, active_page = (
        _load_source_report(layout)
    )

    report = Report(
        name=layout.report_name,
        palette_name=palette_name,
        palette_data=palette_data,
        raw_report_data=raw_report_data,
        dataset_reference=dataset_reference,
        active_page_name=active_page,
    )

    for page_spec in layout.pages:
        merged = _apply_shared(page_spec, layout.shared_rows)
        page_canvas = page_spec.canvas or layout.canvas
        page = _build_page(
            merged, page_canvas, page_id_map,
            source_visuals, source_pages, tokens,
            debug=debug, theme_dir=pkg_theme_dir,
        )
        report.add_page(page)

    if pkg_theme_dir:
        _register_resources(report, layout, tokens, pkg_theme_dir)

    from .info_table import collect_info, build_config_tmdl
    info_items = collect_info(layout, tokens)
    if info_items:
        report.config_table_tmdl = build_config_tmdl(info_items)
        for name, _html, height in info_items:
            report.add_page(_make_tooltip_page(name, tokens, height))

    return report


def _build_palette(palette_tokens: dict) -> dict | None:
    """Extract palette fields from the token dict into the PBIR palette structure."""
    data: dict = {
        "name": palette_tokens["name"],
        "dataColors": palette_tokens["dataColors"],
    }
    for key in (
        "firstLevelElements", "secondLevelElements", "thirdLevelElements",
        "fourthLevelElements", "background", "secondaryBackground",
        "tableAccent", "good", "neutral", "bad",
        "maximum", "center", "minimum", "null", "hyperlink",
        "textClasses", "visualStyles",
    ):
        if key in palette_tokens:
            data[key] = palette_tokens[key]
    return data


def _load_source_report(layout: LayoutSpec):
    """Load the source PBIR report and return (visuals, pages, report_data, dataset, active_page).

    Returns a tuple of Nones when no source path is configured or the path does not exist.
    """
    if not (layout.source_report_path and layout.source_report_path.exists()):
        return None, None, None, None, None

    from ..models import Report as _Report

    src = _Report.from_pbir(layout.source_report_path)
    source_visuals = {v.name: v for page in src.pages for v in page.visuals}
    source_pages = {p.name: p for p in src.pages}
    return source_visuals, source_pages, src.raw_report_data, src.dataset_reference, src.active_page_name
