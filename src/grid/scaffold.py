"""Interactive wizard to add a component to a layout YAML."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from ..components import DEFAULT_HEIGHTS, DEFAULT_SPANS
from ..packages import load_visual_defaults
from .extractor import validate_layout

_THEMES_ROOT = Path(__file__).parent.parent.parent / "themes"
_COMPONENTS = ["header", "footer", "menu"]


# ── Theme helpers ──────────────────────────────────────────────────────────────

def _available_themes() -> list[str]:
    """Return sorted theme names found under the themes/ directory."""
    if not _THEMES_ROOT.is_dir():
        return []
    return sorted(d.name for d in _THEMES_ROOT.iterdir() if d.is_dir())


# ── Prompt helpers ─────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    """Prompt for a string value, returning *default* on empty input."""
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val if val else default


def _ask_int(prompt: str, default: int) -> int:
    """Prompt for an integer value, returning *default* on invalid/empty input."""
    raw = _ask(prompt, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _choose(prompt: str, options: list[str]) -> int:
    """Prompt the user to pick one option by number; returns 0-based index."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    while True:
        raw = _ask("Select").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        print(f"  Enter a number between 1 and {len(options)}.")


def _choose_many(prompt: str, options: list[str]) -> list[int]:
    """Prompt for a comma-separated selection; empty input selects all. Returns 0-based indices."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    raw = _ask("Select (comma-separated, Enter = all)", "")
    if not raw:
        return list(range(len(options)))
    result = []
    for part in raw.split(","):
        try:
            idx = int(part.strip()) - 1
            if 0 <= idx < len(options):
                result.append(idx)
        except ValueError:
            pass
    return result if result else list(range(len(options)))


# ── Component prop builders ────────────────────────────────────────────────────

def _header_props() -> dict:
    """Collect header-specific props from the user."""
    title = _ask("Title", "Report Title")
    subtitle = _ask("Subtitle (blank to skip)", "")
    props: dict = {"title": title}
    if subtitle:
        props["subtitle"] = subtitle
    return props


def _footer_props() -> dict:
    """Collect footer-specific props from the user, including a sample links structure."""
    legal = _ask("Legal text (blank to skip)", "")
    props: dict = {
        "links": [
            {
                "title": "Column 1",
                "items": [
                    {"label": "Link 1", "url": ""},
                    {"label": "Link 2", "url": ""},
                ],
            },
            {
                "title": "Column 2",
                "items": [
                    {"label": "Link 3", "url": ""},
                    {"label": "Link 4", "url": ""},
                ],
            },
        ],
    }
    if legal:
        props["legal"] = legal
    return props


def _menu_props(page_names: list[str], separators: bool = False) -> dict:
    """Collect menu-specific props: page selection and orientation."""
    indices = _choose_many("Select pages to include as menu items (Enter = all)", page_names)
    selected = [page_names[i] for i in indices]
    orientation = ["vertical", "horizontal"][_choose("Orientation", ["vertical", "horizontal"])]
    items: list[dict] = []
    for i, p in enumerate(selected):
        if separators and i > 0:
            items.append({"separator": True})
        items.append({"page": p})
    return {"orientation": orientation, "items": items}


# ── Visual defaults ────────────────────────────────────────────────────────────

def _apply_visual_defaults(data: dict, vis_defaults: dict) -> None:
    """Apply canvas and per-visual-type defaults from the theme without overriding user values."""
    canvas_defs = vis_defaults.get("canvas", {})
    if canvas_defs:
        canvas = data.setdefault("canvas", {})
        for k, v in canvas_defs.items():
            canvas.setdefault(k, v)

    vis_defs = vis_defaults.get("visuals", {})
    if not vis_defs:
        return
    for page in data.get("pages", []):
        for row in page.get("rows", []):
            for col in row.get("cols", []):
                vtype = col.get("visual")
                if vtype and vtype in vis_defs:
                    for k, v in vis_defs[vtype].items():
                        col.setdefault(k, v)


# ── Menu placement ─────────────────────────────────────────────────────────────

def _fit_row_spans(page_rows: list, row_idx: int, rowspan: int, menu_span: int) -> list[str]:
    """Shrink col spans (right-to-left) in each affected row so total fits within 12.

    Returns a list of human-readable adjustment messages.
    """
    msgs: list[str] = []
    for j in range(row_idx, row_idx + rowspan):
        if j >= len(page_rows):
            break
        shrinkable = [c for c in page_rows[j].get("cols", []) if "span" in c]
        overflow = menu_span + sum(c["span"] for c in shrinkable) - 12
        if overflow <= 0:
            continue
        for c in reversed(shrinkable):
            reduction = min(c["span"] - 1, overflow)
            if reduction > 0:
                old_span = c["span"]
                c["span"] -= reduction
                label = c.get("name") or c.get("visual") or "?"
                msgs.append(
                    f"    row '{page_rows[j]['id']}': '{label}' span {old_span} → {c['span']}"
                )
                overflow -= reduction
            if overflow <= 0:
                break
    return msgs


def _place_menu_col(
    comp_name: str,
    span: int,
    total_height: int,
    pages: list[dict],
    target_indices: list[int],
) -> None:
    """Insert the menu as a rowspan column into an existing row on each target page.

    Automatically computes rowspan from the given total_height, adjusts the last
    covered row's height so the sum equals total_height, and shrinks any col spans
    that would overflow the 12-column grid.
    """
    side_idx = _choose("Insert menu column on", ["left side", "right side"])
    prepend = side_idx == 0

    for i in target_indices:
        page_rows: list = pages[i].get("rows", [])
        if not page_rows:
            print(f"  Page '{pages[i].get('display_name', pages[i]['id'])}' has no rows — skipping.")
            continue

        row_labels = [f"[{r['id']}]  h={r.get('height', '?')}" for r in page_rows]
        row_idx = _choose(
            f"Page '{pages[i].get('display_name', pages[i]['id'])}': anchor menu to row",
            row_labels,
        )

        accumulated, rowspan = 0, 0
        for j in range(row_idx, len(page_rows)):
            accumulated += page_rows[j].get("height", 0)
            rowspan += 1
            if accumulated >= total_height:
                break

        # Adjust the last covered row so the rowspan sum equals total_height exactly.
        last_row = page_rows[row_idx + rowspan - 1]
        accumulated_before_last = accumulated - last_row.get("height", 0)
        new_last_height = total_height - accumulated_before_last
        if new_last_height != last_row.get("height", 0):
            old_h = last_row.get("height", 0)
            last_row["height"] = new_last_height
            print(
                f"\n  Auto-fit: row '{last_row['id']}' height {old_h} → {new_last_height}px "
                f"(rowspan sum = {total_height}px)."
            )

        adjustments = _fit_row_spans(page_rows, row_idx, rowspan, span)
        if adjustments:
            print(f"\n  Auto-fit: reduced spans in rows covered by '{comp_name}' (span={span}):")
            for msg in adjustments:
                print(msg)

        col: dict = {"ref": comp_name, "rowspan": rowspan}
        cols: list = page_rows[row_idx].setdefault("cols", [])
        if prepend:
            cols.insert(0, col)
        else:
            cols.append(col)

        print(f"  Added to row '{page_rows[row_idx]['id']}' with rowspan={rowspan}.")


# ── Scaffold phases ────────────────────────────────────────────────────────────

def _select_theme(data: dict, themes: list[str]) -> dict:
    """Prompt to set or change the layout theme; returns updated visual_defaults."""
    current = data.get("package")
    if current:
        if _ask(f"Theme is '{current}'. Change? [y/N]", "N").lower() == "y":
            idx = _choose("Select theme", themes + ["none (remove theme)"])
            data["package"] = themes[idx] if idx < len(themes) else None
            if data["package"] is None:
                data.pop("package", None)
    else:
        idx = _choose("Select theme", themes + ["none"])
        if idx < len(themes):
            data["package"] = themes[idx]

    return load_visual_defaults(data.get("package"))


def _scaffold_component(
    component: str,
    data: dict,
    pages: list[dict],
    page_names: list[str],
    vis_defaults: dict,
) -> str | None:
    """Run the interactive wizard for a single component.

    Returns the shared component name if scaffolded, or None if skipped.
    """
    print(f"\n── Configuring: {component} ──")
    comp_name = _ask("Shared component name", f"page_{component}")
    span = _ask_int("Column span (1-12)", DEFAULT_SPANS.get(component, 12))
    height = _ask_int("Row height (canvas units)", DEFAULT_HEIGHTS.get(component, 60))

    comp_defaults = vis_defaults.get("components", {}).get(component, {})
    if component == "header":
        extra = _header_props()
    elif component == "footer":
        extra = _footer_props()
    else:
        extra = _menu_props(page_names, separators=comp_defaults.get("separator_between_items", False))

    _INTERNAL_KEYS = {"separator_between_items"}
    comp_def: dict = {
        "span": span,
        "component": component,
        **{k: v for k, v in comp_defaults.items() if k not in _INTERNAL_KEYS},
        **extra,
    }

    shared = data.setdefault("shared", {})
    components = shared.setdefault("components", {})
    if comp_name in components:
        if _ask(f"'{comp_name}' already exists. Overwrite? [y/N]", "N").lower() != "y":
            print(f"Skipping '{comp_name}'.")
            return None
    components[comp_name] = comp_def

    add_idx = _choose(
        f"Add '{comp_name}' to pages?",
        ["All pages", "Select pages", "Skip — add manually"],
    )
    if add_idx < 2:
        target_indices = (
            list(range(len(pages)))
            if add_idx == 0
            else _choose_many("Select pages", page_names)
        )
        if component == "menu":
            _place_menu_col(comp_name, span, height, pages, target_indices)
        else:
            position_idx = _choose("Insert row at", ["top", "bottom"])
            base_row_id = f"{comp_name}_row"
            for i in target_indices:
                page_rows: list = pages[i].setdefault("rows", [])
                existing_ids = {r.get("id") for r in page_rows}
                rid, n = base_row_id, 1
                while rid in existing_ids:
                    rid, n = f"{base_row_id}_{n}", n + 1
                new_row = {"id": rid, "height": height, "cols": [{"ref": comp_name}]}
                if position_idx == 0:
                    page_rows.insert(0, new_row)
                else:
                    page_rows.append(new_row)

    return comp_name


# ── Public API ─────────────────────────────────────────────────────────────────

def scaffold(layout_path: Path) -> None:
    """Interactively add components (header, footer, menu) to a layout YAML.

    Guides the user through theme selection, component configuration, and page
    placement. Validates heights and saves the updated YAML on completion.
    """
    if not layout_path.exists():
        print(f"Error: layout file not found: {layout_path}", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(layout_path.read_text(encoding="utf-8")) or {}
    pages: list[dict] = data.get("pages", [])
    page_names = [p.get("display_name", p["id"]) for p in pages]

    # Phase 1: Theme
    themes = _available_themes()
    vis_defaults: dict = {}
    if themes:
        vis_defaults = _select_theme(data, themes)
        if vis_defaults:
            _apply_visual_defaults(data, vis_defaults)

    # Phase 2: Components
    comp_indices = _choose_many("Select components to add (Enter = all)", _COMPONENTS)
    scaffolded: list[str] = []

    for component in [_COMPONENTS[i] for i in comp_indices]:
        name = _scaffold_component(component, data, pages, page_names, vis_defaults)
        if name:
            scaffolded.append(f"'{name}' ({component})")

    # Phase 3: Validate and save
    validate_layout(data)
    layout_path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    if scaffolded:
        print(f"\nScaffolded {', '.join(scaffolded)} in {layout_path}")
