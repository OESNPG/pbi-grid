"""Static `pbi_grid_config` table generation for the per-visual info modal.

The "HTML Content (lite)" custom visual renders a **column of a table**, not a
measure. So the info modal of each component is fed by a one-row static table
`pbi_grid_config` with one column ``info_<visual>`` per component holding the ready
HTML (a modal card), plus an ``icon`` measure ("ⓘ") used by the small trigger card.
pbi-grid builds the HTML here (template in Python) and writes the table's TMDL into
the SemanticModel at generate time, registering it in model.tmdl.

The hidden tooltip page of each component binds an HTML Content visual to its
``pbi_grid_config[info_<visual>]`` column, and a small ``cardVisual`` (the ⓘ) carries
a report-page tooltip to that page (see the engine).
"""
from __future__ import annotations

import math
import re
import uuid

from .schema import LayoutSpec

# Name of the generated table. Distinct from any user table so the source project
# can drop its own `config` table — pbi-grid owns `pbi_grid_config` end to end.
TABLE_NAME = "pbi_grid_config"
# Stable lineageTag derived from the name (so per-column GUIDs are reproducible).
TABLE_LINEAGE = str(uuid.uuid5(uuid.NAMESPACE_OID, TABLE_NAME))
_NS = uuid.UUID(TABLE_LINEAGE)

ICON_GLYPH = "ⓘ"
ICON_MEASURE = "icon"
HTML_CONTENT_VISUAL_TYPE = "htmlContent443BE3AD55E043BF878BED274D3A6865"


def info_column(visual_name: str) -> str:
    """Config-table column that holds a visual's modal HTML."""
    return f"info_{visual_name}"


def _gid(prefix: str, name: str) -> str:
    """Deterministic 20-hex id (page/visual) derived from a visual name."""
    return uuid.uuid5(_NS, f"{prefix}:{name}").hex[:20]


def info_page_id(name: str) -> str:
    """PBIR page name of a component's hidden info tooltip page."""
    return _gid("page", name)


def info_icon_id(name: str) -> str:
    """PBIR visual name of a component's ⓘ trigger card."""
    return _gid("icon", name)


def tooltip_visual_id(name: str) -> str:
    """PBIR visual name of the HTML Content visual on a tooltip page."""
    return _gid("ttvis", name)


def _norm(value: str | None) -> str:
    """Collapse whitespace runs to a single space; None -> ''."""
    return " ".join(value.split()) if value else ""


def _m_escape(s: str) -> str:
    """Escape an M string literal (double the double-quotes)."""
    return s.replace('"', '""')


def _text_lines(text: str, font: int, text_w: float) -> int:
    """Rough wrapped-line count for *text* at *font* px within *text_w* px."""
    if not text:
        return 1
    cpl = max(1, int(text_w / (font * 0.52)))  # ~0.52 px-per-char for a proportional font
    return max(1, math.ceil(len(text) / cpl))


def estimate_modal_height(
    description: str, *,
    width: float, body_font: int, padding: int,
    content_scale: float = 1.25, min_height: float = 90,
) -> int:
    """Estimate the modal card height (px) and add a buffer so it never scrolls.

    Height is unknown until rendered, so we approximate from text length and the
    theme font/padding, then scale by ``content_scale`` (e.g. 1.25 = window 25%
    larger than the content). The HTML Content visual can't be scrolled inside a
    tooltip, so over-sizing slightly is the safe side.
    """
    text_w = max(40.0, width - 2 * padding - 6)
    body_h = _text_lines(description, body_font, text_w) * body_font * 1.45
    content = 2 * padding + body_h
    return int(round(max(min_height, content * content_scale)))


def build_info_html(
    description: str, *,
    body_font: int = 10, padding: int = 8,
) -> str:
    """Minimalist modal HTML: just the ``description`` text — no title/heading,
    no header background, border, shadow, footer or icon.

    Font size (px) and padding are theme-driven (``info_modal`` tokens) so the
    text stays proportional to the tooltip page size.
    """
    body = (
        f"<div style='font-size:{body_font}px;line-height:1.45;color:#212529;"
        f"text-align:justify;'>{description}</div>"
    )
    return (
        f"<div style='background:#ffffff;padding:{padding}px;"
        "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'>"
        f"{body}</div>"
    )


def collect_info(layout: LayoutSpec, tokens: dict | None = None) -> list[tuple[str, str, int]]:
    """(visual_name, html, height) for every layout col with a ``config:`` + ``name``.

    The body is ``info`` (a plain description) — the modal shows only that, with
    no title. ``height`` is the estimated tooltip-page height (with the
    content-scale buffer) so the modal doesn't scroll. Cols without an ``info``
    description are skipped (no modal to show).
    """
    style = (tokens or {}).get("info_modal", {}) or {}
    style_kw = {k: style[k] for k in ("body_font", "padding") if k in style}
    width = float(style.get("width", 230))
    bf = int(style.get("body_font", 10)); pad = int(style.get("padding", 8))
    scale = float(style.get("content_scale", 1.25)); minh = float(style.get("min_height", 90))
    out: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for page in layout.pages:
        for row in page.rows:
            for col in row.cols:
                if not (col.config and col.name) or col.name in seen:
                    continue
                desc = _norm(col.config.info)
                if not desc:
                    continue
                html = build_info_html(desc, **style_kw)
                height = estimate_modal_height(
                    desc, width=width, body_font=bf,
                    padding=pad, content_scale=scale, min_height=minh,
                )
                out.append((col.name, html, height))
                seen.add(col.name)
    return out


def _column_block(col_name: str) -> str:
    lt = uuid.uuid5(_NS, col_name)
    return (
        f"\tcolumn {col_name}\n"
        f"\t\tdataType: string\n"
        f"\t\tlineageTag: {lt}\n"
        f"\t\tsummarizeBy: none\n"
        f"\t\tsourceColumn: {col_name}\n\n"
        f"\t\tannotation SummarizationSetBy = Automatic"
    )


def _icon_measure_block() -> str:
    lt = uuid.uuid5(_NS, "measure:icon")
    return (
        f'\tmeasure {ICON_MEASURE} = "{ICON_GLYPH}"\n'
        f"\t\tlineageTag: {lt}"
    )


def build_config_tmdl(items: list[tuple[str, str]]) -> str:
    """TMDL for the one-row static table (one info col per visual + an `icon` measure)."""
    col_names = [info_column(t[0]) for t in items]
    values = [t[1] for t in items]

    columns = "\n\n".join(_column_block(cn) for cn in col_names)
    type_lines = ",\n".join(f"                            {cn} = text" for cn in col_names)
    value_lines = ",\n".join(f'                                "{_m_escape(v)}"' for v in values)

    return (
        f"table {TABLE_NAME}\n"
        f"\tlineageTag: {TABLE_LINEAGE}\n\n"
        f"{columns}\n\n"
        f"{_icon_measure_block()}\n\n"
        f"\tpartition {TABLE_NAME} = m\n"
        f"\t\tmode: import\n"
        f"\t\tsource =\n"
        f"\t\t\tlet\n"
        f"\t\t\t    data = #table(\n"
        f"\t\t\t        type table [\n"
        f"{type_lines}\n"
        f"\t\t\t        ],\n"
        f"\t\t\t        {{\n"
        f"\t\t\t            {{\n"
        f"{value_lines}\n"
        f"\t\t\t            }}\n"
        f"\t\t\t        }}\n"
        f"\t\t\t    )\n"
        f"\t\t\tin\n"
        f"\t\t\t    data\n\n"
        f"\tannotation PBI_NavigationStepName = Navegação\n\n"
        f"\tannotation PBI_ResultType = Table\n"
    )


def register_config_in_model(model_text: str, table: str = TABLE_NAME) -> str:
    """Ensure the model.tmdl references the generated table, idempotently.

    pbi-grid generates only the table *file* (``tables/<table>.tmdl``); the model
    declares its tables via ``ref table <name>`` (and an optional ``PBI_QueryOrder``
    annotation). Adding the reference here lets the source project drop the table —
    pbi-grid re-registers it in the generated output. Returns the text unchanged
    when the table is already registered.
    """
    text = model_text
    if not re.search(rf"(?m)^ref table {re.escape(table)}\s*$", text):
        refs = list(re.finditer(r"(?m)^ref table .+$", text))
        if refs:
            i = refs[-1].end()
            text = text[:i] + f"\nref table {table}" + text[i:]
        else:
            text = text.rstrip("\n") + f"\n\nref table {table}\n"
    m = re.search(r"(?m)^(\s*annotation PBI_QueryOrder = \[)(.*?)(\]\s*)$", text)
    if m and f'"{table}"' not in m.group(2):
        inner = m.group(2)
        sep = "," if inner.strip() else ""
        text = text[: m.start()] + m.group(1) + inner + sep + f'"{table}"' + m.group(3) + text[m.end():]
    return text