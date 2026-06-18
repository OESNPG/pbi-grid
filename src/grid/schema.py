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
class OverlaySpec:
    """A visual rendered on top of its parent cell (higher z), aligned within it.

    Use for things Power BI has no native support for — e.g. a discreet total card
    centered in a donut's hole. Size is in px; omitted dimensions fill the cell.
    """
    name: str | None = None       # PBIR visual name (existing visual) — preferred
    visual: str | None = None     # Power BI visual type (when creating a bare visual)
    width: float | None = None    # px; defaults to the full parent cell width
    height: float | None = None   # px; defaults to the full parent cell height
    align: str = "center"         # horizontal: left | center | right
    valign: str = "center"        # vertical:   top  | center | bottom
    offset_x: float = 0.0         # px nudge after alignment (can be negative)
    offset_y: float = 0.0         # px nudge after alignment (e.g. push the card down
                                  # past a donut's title/legend at the top)


@dataclass
class IconSpec:
    """Override for the ⓘ info-icon placement — the icon analogue of ``overlay``.

    Positioned within the cell like an overlay (align/valign + offset). If no
    align/valign/offset is given, the theme-default placement for the visual
    type is kept (``size`` still applies). Handy on slicers so the ⓘ clears the
    header's clear-selection ("eraser") button.
    """
    size: float | None = None
    align: str | None = None      # left | center | right (default right)
    valign: str | None = None     # top  | center | bottom (default top)
    offset_x: float = 0.0
    offset_y: float = 0.0


@dataclass
class InfoSpec:
    """Documentation block of a visual's config (rendered later as a help modal)."""
    title: str | None = None
    description: str | None = None   # HTML body
    footer: str | None = None


@dataclass
class ColConfig:
    """Presentation/config of a visual, parsed from its ``config:`` YAML file.

    ``title`` is injected as the visual's header title; ``footer`` is a caption
    below the visual; ``info`` documents the component for the help modal. All
    fields are optional (empty = not applied).
    """
    title: str | None = None
    footer: str | None = None
    info: InfoSpec = field(default_factory=InfoSpec)


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
    overlay: list[OverlaySpec] = field(default_factory=list)  # visuals stacked on top of this cell
    config: ColConfig | None = None  # presentation config (RESOLVED from the `config:` YAML at parse time)
    info_icon: "IconSpec | None" = None  # override for the ⓘ placement (like overlay, for the icon)
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
    canvas: "Canvas | None" = None   # canvas próprio da página; campos omitidos herdam do canvas global


# ── YAML parsing helpers ───────────────────────────────────────────────────────

_KNOWN_COL_KEYS = {
    "span", "name", "component", "visual", "rowspan", "ref",
    "height", "valign", "border", "border_color", "border_weight", "overlay", "config", "info_icon",
}


def _resolve_config(path_str: str | None, base_dir: Path | None) -> ColConfig | None:
    """Load a col's ``config:`` YAML (title/footer/info), relative to the layout dir.

    Tries the exact path, then ``.yaml`` / ``.yml``. Returns a ColConfig, or None
    (with a warning) when no file is found. Reading at parse time means edits to
    the config are picked up on the next ``generate``. Empty/blank fields become
    None so the engine can treat them as "not applied".
    """
    if not path_str:
        return None
    p = Path(path_str)
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / path_str
    candidates = [p]
    if p.suffix == "":
        candidates += [p.with_suffix(".yaml"), p.with_suffix(".yml")]
    for c in candidates:
        if c.exists():
            raw = yaml.safe_load(c.read_text(encoding="utf-8")) or {}
            info_raw = raw.get("info") or {}
            return ColConfig(
                title=_clean(raw.get("title")),
                footer=_clean(raw.get("footer")),
                info=InfoSpec(
                    title=_clean(info_raw.get("title")),
                    description=_clean(info_raw.get("description")),
                    footer=_clean(info_raw.get("footer")),
                ),
            )
    print(f"  WARNING: config file not found for '{path_str}' (tried: {', '.join(str(c) for c in candidates)})")
    return None


def _clean(value: Any) -> str | None:
    """Strip a YAML string field; treat empty/whitespace-only as None."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _make_overlayspec(raw: dict[str, Any]) -> OverlaySpec:
    """Parse one overlay dict into an OverlaySpec."""
    rw = raw.get("width")
    rh = raw.get("height")
    return OverlaySpec(
        name=raw.get("name"),
        visual=raw.get("visual"),
        width=float(rw) if rw is not None else None,
        height=float(rh) if rh is not None else None,
        align=raw.get("align", "center"),
        valign=raw.get("valign", "center"),
        offset_x=float(raw.get("offset_x", 0) or 0),
        offset_y=float(raw.get("offset_y", 0) or 0),
    )


def _make_iconspec(raw: dict[str, Any] | None) -> "IconSpec | None":
    """Parse a col's ``info_icon`` dict into an IconSpec (None when absent)."""
    if not raw:
        return None
    rs = raw.get("size")
    return IconSpec(
        size=float(rs) if rs is not None else None,
        align=raw.get("align"),
        valign=raw.get("valign"),
        offset_x=float(raw.get("offset_x", 0) or 0),
        offset_y=float(raw.get("offset_y", 0) or 0),
    )


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


def _make_colspec(
    col_raw: dict[str, Any],
    shared_components: dict[str, dict[str, Any]],
    base_dir: Path | None = None,
) -> ColSpec:
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
        overlay=[_make_overlayspec(o) for o in col_raw.get("overlay", [])],
        config=_resolve_config(col_raw.get("config"), base_dir),
        info_icon=_make_iconspec(col_raw.get("info_icon")),
        props={k: v for k, v in col_raw.items() if k not in _KNOWN_COL_KEYS},
    )


def _parse_rows(
    rows_raw: list[dict],
    shared_components: dict[str, dict[str, Any]],
    base_dir: Path | None = None,
) -> list[RowSpec]:
    """Parse a list of row dicts into RowSpec objects."""
    rows: list[RowSpec] = []
    for row_raw in rows_raw:
        cols = [_make_colspec(c, shared_components, base_dir) for c in row_raw.get("cols", [])]
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
        base_dir = path.parent  # `config:` paths resolve relative to the layout file

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
                cols=[_make_colspec(c, shared_components, base_dir) for c in row_raw.get("cols", [])],
                height=row_raw.get("height", 0),
            )
            for row_raw in data.get("shared", {}).get("rows", [])
        ]

        def _page_canvas(page_raw: dict) -> Canvas | None:
            """Canvas próprio da página (herda do global os campos omitidos), ou None."""
            pc = page_raw.get("canvas")
            if not pc:
                return None
            return Canvas(
                width=pc.get("width", canvas.width),
                height=pc.get("height", canvas.height),
                gutter=pc.get("gutter", canvas.gutter),
            )

        pages: list[PageSpec] = [
            PageSpec(
                id=page_raw["id"],
                display_name=page_raw.get("display_name", page_raw["id"]),
                rows=_parse_rows(page_raw.get("rows", []), shared_components, base_dir),
                canvas=_page_canvas(page_raw),
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
