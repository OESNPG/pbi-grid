from dataclasses import dataclass, field
from pathlib import Path

from .base import Component, TokenMixin
from ..grid.schema import Cell
from ..models import Visual, Position
from ..pbir_utils import make_id, literal, hex_color, theme_color

_CHILD_INDENT = 12.0  # px left-indent for nested (child) menu items


@dataclass
class MenuItem:
    page: str = ""
    description: str = ""
    icon: str = ""            # filename relative to theme dir (e.g. "icons/home.png")
    items: list["MenuItem"] = field(default_factory=list)
    is_separator: bool = False

    @property
    def is_group(self) -> bool:
        """True when this item has sub-items (renders as a non-clickable header)."""
        return bool(self.items)


def _flatten(items: list[MenuItem]) -> list[tuple[MenuItem, bool]]:
    """Return (item, is_child) pairs in display order.

    Separators pass through as-is. Group headers produce one entry with
    is_child=False followed by their children with is_child=True.
    Leaf items produce one entry with is_child=False.
    """
    result: list[tuple[MenuItem, bool]] = []
    for item in items:
        if item.is_separator:
            result.append((item, False))
        elif item.is_group:
            result.append((item, False))
            for sub in item.items:
                result.append((sub, True))
        else:
            result.append((item, False))
    return result


@dataclass
class MenuComponent(TokenMixin, Component):
    """Dynamic navigation menu with optional two-level grouping, icons, and separators.

    Flat items navigate directly via Power BI page links. Group items render as
    non-clickable section headers followed by indented child buttons. Separator
    items render as thin horizontal divider lines.
    """

    items: list[MenuItem]
    orientation: str = "vertical"
    page_id_map: dict[str, str] = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)
    theme_dir: Path | None = None

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _color(self, *keys: str, fallback_id: int, fallback_percent: float = 0.0) -> dict:
        """Return a hex color expression from tokens, or a ThemeDataColor fallback."""
        d = self.tokens
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return theme_color(fallback_id, fallback_percent)
            d = d[key]
        return hex_color(d) if isinstance(d, str) else theme_color(fallback_id, fallback_percent)

    def _font_size(self) -> int:
        """Return font size from token, defaulting to 14 for horizontal and 10 for vertical."""
        v = self._token_int("menu", "item", "font_size", default=0)
        return v if v > 0 else (14 if self.orientation == "horizontal" else 10)

    def _font_family_literal(self) -> str:
        """Return the DAX literal string for the button font family.

        Token value is a plain CSS font-family string; single quotes are escaped
        for the DAX literal format (e.g. 'Rawline, ''Segoe UI'', sans-serif').
        """
        v = self._token_str("menu", "item", "font_family")
        if v:
            return "'" + v.replace("'", "''") + "'"
        return "'''Segoe UI Bold'', wf_segoe-ui_bold, helvetica, arial, sans-serif'"

    # ------------------------------------------------------------------
    # Slot height layout
    # ------------------------------------------------------------------

    def _item_height(self) -> float:
        return float(self._token_int("menu", "item_height", default=48))

    def _separator_height(self) -> float:
        line_h = float(self._token_int("menu", "separator_height", default=1))
        margin = float(self._token_int("menu", "separator_margin", default=8))
        return line_h + 2 * margin

    def _icon_size(self) -> float:
        return float(self._token_int("menu", "icon_size", default=20))

    def _icon_padding(self) -> float:
        return float(self._token_int("menu", "icon_padding", default=8))

    def _slot_heights(self, flat: list[tuple[MenuItem, bool]]) -> list[float]:
        """Return the pixel height for each flat slot (separator vs regular item)."""
        item_h, sep_h = self._item_height(), self._separator_height()
        return [sep_h if item.is_separator else item_h for item, _ in flat]

    def _effective_cell(self, cell: Cell, slot_heights: list[float]) -> Cell:
        """Shrink cell height to content height when items are shorter than the rowspan."""
        total_h = round(sum(slot_heights), 4)
        if total_h < cell.height:
            return Cell(x=cell.x, y=cell.y, width=cell.width, height=total_h, z=cell.z)
        return cell

    def _slot_cell(self, cell: Cell, slot: int, slot_heights: list[float], is_child: bool) -> Cell:
        """Return the Cell for a single menu slot in either orientation."""
        if self.orientation == "vertical":
            y_off = sum(slot_heights[:slot])
            indent = _CHILD_INDENT if is_child else 0.0
            return Cell(
                x=cell.x + indent,
                y=round(cell.y + y_off, 4),
                width=cell.width - indent,
                height=round(slot_heights[slot], 4),
                z=cell.z + slot * 100,
            )
        item_w = cell.width / len(slot_heights)
        return Cell(
            x=round(cell.x + slot * item_w, 4),
            y=cell.y,
            width=round(item_w, 4),
            height=cell.height,
            z=cell.z + slot * 100,
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def resolve(self, cell: Cell) -> list[Visual]:
        """Render all menu items into PBIR visuals."""
        flat = _flatten(self.items)
        if not flat:
            return []

        slot_heights = self._slot_heights(flat)
        cell = self._effective_cell(cell, slot_heights)
        visuals: list[Visual] = []

        bg_color = self._token_str("menu", "background_color")
        if bg_color:
            visuals.append(self._make_background(cell, bg_color))

        for slot, (item, is_child) in enumerate(flat):
            item_cell = self._slot_cell(cell, slot, slot_heights, is_child)
            if item.is_separator:
                visuals.append(self._make_separator(item_cell, slot))
            elif item.is_group:
                visuals.append(self._make_header(item, item_cell, slot))
            else:
                icon_visual = self._make_icon(item, item_cell, slot)
                icon_reserved = (self._icon_size() + self._icon_padding()) if icon_visual else 0.0
                visuals.append(self._make_button(item, item_cell, slot, is_child, icon_reserved))
                if icon_visual:
                    visuals.append(icon_visual)

        return visuals

    # ------------------------------------------------------------------
    # Separator
    # ------------------------------------------------------------------

    def _make_separator(self, cell: Cell, slot: int) -> Visual:
        """Thin horizontal line rendered between menu sections."""
        sep_color = self._token_str("menu", "separator_color") or "#E0E0E0"
        sep_h = float(self._token_int("menu", "separator_height", default=1))
        margin = float(self._token_int("menu", "separator_margin", default=8))
        return Visual(
            name=make_id(f"menu-sep-{cell.z}-{slot}"),
            visual_type="shape",
            position=Position(
                x=cell.x, y=round(cell.y + margin, 4), z=cell.z,
                width=cell.width, height=sep_h, tab_order=cell.z,
            ),
            config={
                "objects": {
                    "fill": [
                        {"properties": {
                            "show": literal("true"),
                            "fillColor": hex_color(sep_color),
                            "transparency": literal("0D"),
                        }},
                        {"properties": {"fillColor": hex_color(sep_color)}, "selector": {"id": "default"}},
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

    # ------------------------------------------------------------------
    # Icon
    # ------------------------------------------------------------------

    def _make_icon(self, item: MenuItem, cell: Cell, slot: int) -> Visual | None:
        """Image visual for the menu item icon; None when no icon file is configured."""
        if not item.icon or not self.theme_dir:
            return None
        icon_file = self.theme_dir / item.icon
        if not icon_file.exists():
            return None

        icon_size = self._icon_size()
        padding = self._icon_padding()
        icon_x = round(cell.x + padding, 4)
        icon_y = round(cell.y + (cell.height - icon_size) / 2, 4)
        return Visual(
            name=make_id(f"menu-icon-{item.icon}-{cell.z}-{slot}"),
            visual_type="image",
            position=Position(
                x=icon_x, y=icon_y, z=cell.z + 1,
                width=icon_size, height=icon_size, tab_order=cell.z + 1,
            ),
            config={
                "objects": {"general": [{"properties": {
                    "imageUrl": {"expr": {"ResourcePackageItem": {
                        "PackageName": "RegisteredResources",
                        "PackageType": 1,
                        "ItemName": Path(item.icon).name,
                    }}}
                }}]},
                "visualContainerObjects": {
                    "title": [{"properties": {"show": literal("false")}}],
                },
                "drillFilterOtherVisuals": True,
            },
        )

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def _make_background(self, cell: Cell, color: str) -> Visual:
        """Solid filled rectangle behind all menu items."""
        return Visual(
            name=make_id(f"menu-bg-{cell.z}"),
            visual_type="shape",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z - 1,
                width=cell.width, height=cell.height, tab_order=cell.z - 1,
            ),
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
                "drillFilterOtherVisuals": True,
            },
        )

    # ------------------------------------------------------------------
    # Group header
    # ------------------------------------------------------------------

    def _make_header(self, item: MenuItem, cell: Cell, slot: int) -> Visual:
        """Non-clickable section header button for group items."""
        header_bg = self._token_str("menu", "header", "background_color")
        fill_entries = (
            [{"properties": {
                "show": literal("true"),
                "fillColor": hex_color(header_bg),
                "transparency": literal("0D"),
            }}]
            if header_bg else
            [{"properties": {"show": literal("false")}}]
        )
        return Visual(
            name=make_id(f"menu-header-{item.page}-{cell.z}-{slot}"),
            visual_type="actionButton",
            position=Position(x=cell.x, y=cell.y, z=cell.z, width=cell.width, height=cell.height, tab_order=cell.z),
            config={
                "objects": {
                    "text": [
                        {"properties": {"show": literal("true")}},
                        {"properties": {
                            "text": literal(f"'{item.page}'"),
                            "fontColor": self._color("menu", "header", "font_color", fallback_id=1),
                            "verticalAlignment": literal("'middle'"),
                            "horizontalAlignment": literal("'left'"),
                            "fontSize": literal("10D"),
                            "fontFamily": literal(
                                "'''Segoe UI Bold'', wf_segoe-ui_bold, helvetica, arial, sans-serif'"
                            ),
                            "leftMargin": literal("7L"),
                        }, "selector": {"id": "default"}},
                    ],
                    "fill": fill_entries,
                    "outline": [{"properties": {"show": literal("false")}}],
                    "icon": [{"properties": {"show": literal("false")}}],
                },
                "visualContainerObjects": {
                    "visualLink": [{"properties": {
                        "show": literal("false"),
                        "type": literal("'PageNavigation'"),
                    }}],
                    "visualHeader": [{"properties": {"show": literal("false")}}],
                },
            },
        )

    # ------------------------------------------------------------------
    # Navigation button
    # ------------------------------------------------------------------

    def _button_fill(self, is_child: bool) -> list[dict]:
        """Build the fill state array for default / hover / selected states."""
        if self.orientation == "horizontal":
            hover_fill = self._color("menu", "item", "fill_color_hover", fallback_id=3, fallback_percent=0.4)
            sel_fill = self._color("menu", "item", "fill_color_selected", fallback_id=3)
            return [
                {"properties": {"show": literal("false")}},
                {"properties": {"show": literal("true"), "fillColor": hover_fill}, "selector": {"id": "hover"}},
                {"properties": {"show": literal("true"), "fillColor": sel_fill}, "selector": {"id": "selected"}},
            ]
        default_fill = self._token_str("menu", "item", "fill_color_default") if is_child else None
        base = (
            [{"properties": {
                "show": literal("true"),
                "fillColor": hex_color(default_fill),
                "transparency": literal("0D"),
            }}]
            if default_fill else
            [{"properties": {"show": literal("false")}}]
        )
        return base + [
            {"properties": {
                "fillColor": self._color("menu", "item", "fill_color_hover", fallback_id=3, fallback_percent=0.4),
                "transparency": literal("84D"),
            }, "selector": {"id": "hover"}},
            {"properties": {
                "fillColor": self._color("menu", "item", "fill_color_selected", fallback_id=3),
                "transparency": literal("0D"),
            }, "selector": {"id": "selected"}},
        ]

    def _make_button(
        self,
        item: MenuItem,
        cell: Cell,
        index: int,
        is_child: bool = False,
        icon_reserved: float = 0.0,
    ) -> Visual:
        """Page-navigation action button for a leaf menu item."""
        page_id = self.page_id_map.get(item.page, "")
        is_horizontal = self.orientation == "horizontal"
        font_size = self._font_size()
        h_align = "'center'" if is_horizontal else "'left'"
        left_margin = 0 if is_horizontal else (int(icon_reserved + self._icon_padding()) if icon_reserved > 0 else 7)

        general_props: dict = {"keepLayerOrder": literal("true")}
        if item.description:
            general_props["altText"] = literal(f"'{item.description}'")

        visual_link_props: dict = {
            "show": literal("true"),
            "type": literal("'PageNavigation'"),
            "navigationSection": literal(f"'{page_id}'"),
        }
        if item.description:
            visual_link_props["tooltip"] = literal(f"'{item.description}'")

        if is_horizontal:
            font_color_default = self._color("menu", "item", "font_color_default", fallback_id=3, fallback_percent=0.2)
            font_color_hover = self._color("menu", "item", "font_color_hover", fallback_id=3, fallback_percent=0.4)
            font_color_selected = self._color("menu", "item", "font_color_selected", fallback_id=3)
            accent_color = self._color("menu", "item", "accent_color", fallback_id=3)
            drop_shadow = [{"properties": {"show": literal("false")}}]
            outline = [
                {"properties": {"show": literal("false")}},
                {"properties": {
                    "show": literal("true"),
                    "lineColor": accent_color,
                    "weight": literal("3D"),
                }, "selector": {"id": "selected"}},
            ]
        else:
            font_color_default = self._color("menu", "item", "font_color_default", fallback_id=3, fallback_percent=0.2)
            font_color_hover = self._color("menu", "item", "font_color_hover", fallback_id=3, fallback_percent=0.4)
            font_color_selected = self._color("menu", "item", "font_color_selected", fallback_id=3)
            drop_shadow = [{"properties": {
                "show": literal("false"),
                "preset": literal("'Custom'"),
                "position": literal("'Inner'"),
                "color": self._color("menu", "item", "fill_color_selected", fallback_id=3),
                "transparency": literal("0D"),
                "shadowSpread": literal("0D"),
                "shadowBlur": literal("0D"),
                "angle": literal("90D"),
                "shadowDistance": literal("3D"),
            }}]
            outline = [
                {"properties": {"show": literal("false")}},
                {"properties": {
                    "lineColor": self._color("menu", "item", "outline_color", fallback_id=8),
                    "weight": literal("5D"),
                }, "selector": {"id": "default"}},
            ]

        text_props: dict = {
            "text": literal(f"'{item.page}'"),
            "fontColor": font_color_default,
            "verticalAlignment": literal("'middle'"),
            "horizontalAlignment": literal(h_align),
            "fontSize": literal(f"{font_size}D"),
            "fontFamily": literal(self._font_family_literal()),
        }
        if left_margin > 0:
            text_props["leftMargin"] = literal(f"{left_margin}L")

        return Visual(
            name=make_id(f"menu-{item.page}-{cell.z}-{index}"),
            visual_type="actionButton",
            position=Position(x=cell.x, y=cell.y, z=cell.z, width=cell.width, height=cell.height, tab_order=cell.z),
            config={
                "objects": {
                    "icon": [
                        {"properties": {"shapeType": literal("'blank'")}, "selector": {"id": "default"}},
                        {"properties": {"show": literal("false")}},
                    ],
                    "outline": outline,
                    "text": [
                        {"properties": {"show": literal("true")}},
                        {"properties": text_props, "selector": {"id": "default"}},
                        {"properties": {"fontColor": font_color_hover}, "selector": {"id": "hover"}},
                        {"properties": {"fontColor": font_color_selected}, "selector": {"id": "selected"}},
                    ],
                    "fill": self._button_fill(is_child),
                },
                "visualContainerObjects": {
                    "dropShadow": drop_shadow,
                    "title": [{"properties": {
                        "text": literal(f"'{item.page}'"),
                        "titleWrap": literal("true"),
                    }}],
                    "background": [{"properties": {"show": literal("false"), "transparency": literal("0D")}}],
                    "general": [{"properties": general_props}],
                    "border": [{"properties": {"show": literal("false")}}],
                    "visualHeader": [{"properties": {"show": literal("false")}}],
                    "visualLink": [{"properties": visual_link_props}],
                },
                "drillFilterOtherVisuals": True,
            },
        )
