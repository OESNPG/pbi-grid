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


def build_info_html(title: str, description: str, footer: str) -> str:
    """Modal card HTML for one component's info (header/footer #E6E6E6)."""
    return (
        "<div style='border:1px solid #d0d7de;border-radius:8px;overflow:hidden;"
        "background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "box-shadow:0 2px 4px rgba(0,0,0,.08);'>"
        "<div style='background:#E6E6E6;color:#212529;padding:12px 16px;font-size:16px;font-weight:600;'>"
        f"&#8505;&#65039; {title}</div>"
        "<div style='padding:16px;color:#212529;font-size:14px;line-height:1.6;text-align:justify;'>"
        f"{description}</div>"
        "<div style='background:#E6E6E6;border-top:1px solid #d0d7de;padding:12px 16px;color:#6c757d;font-size:12px;'>"
        f"{footer}</div>"
        "</div>"
    )


def collect_info(layout: LayoutSpec) -> list[tuple[str, str]]:
    """(visual_name, html) for every layout col with a ``config:`` and a ``name``.

    The modal title falls back to the visual's ``title`` when ``info.title`` is
    empty, so the header is never blank.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for page in layout.pages:
        for row in page.rows:
            for col in row.cols:
                if not (col.config and col.name) or col.name in seen:
                    continue
                info = col.config.info
                title = _norm(info.title) or _norm(col.config.title)
                html = build_info_html(title, _norm(info.description), _norm(info.footer))
                out.append((col.name, html))
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
    col_names = [info_column(name) for name, _ in items]
    values = [html for _, html in items]

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