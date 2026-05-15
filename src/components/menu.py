import hashlib
from dataclasses import dataclass, field

from .base import Component
from ..grid.schema import Cell
from ..models import Visual, Position


def _make_id(seed: str) -> str:
    return hashlib.md5(seed.encode()).hexdigest()[:20]


def _literal(value: str) -> dict:
    """Wrap a string in the Power BI PBIR Literal expression format."""
    return {"expr": {"Literal": {"Value": value}}}


def _theme_color(color_id: int, percent: float) -> dict:
    """ThemeDataColor expression used as fallback when no token is defined."""
    return {
        "solid": {
            "color": {
                "expr": {
                    "ThemeDataColor": {"ColorId": color_id, "Percent": percent}
                }
            }
        }
    }


def _hex_color(hex_value: str) -> dict:
    """Fixed hex color expression for PBIR (e.g. '#1351B4')."""
    return {
        "solid": {
            "color": {
                "expr": {
                    "Literal": {"Value": f"'{hex_value}'"}
                }
            }
        }
    }


@dataclass
class MenuItem:
    page: str           # display_name ou label do item
    description: str = ""
    items: list["MenuItem"] = field(default_factory=list)

    @property
    def is_group(self) -> bool:
        return bool(self.items)


_CHILD_INDENT = 12.0  # px indent for child items


def _flatten(items: list[MenuItem]) -> list[tuple[MenuItem, bool]]:
    """Return (item, is_child) pairs in display order.

    Group headers produce one entry with is_child=False, followed by their
    children with is_child=True. Leaf items produce one entry with is_child=False.
    """
    result: list[tuple[MenuItem, bool]] = []
    for item in items:
        if item.is_group:
            result.append((item, False))
            for sub in item.items:
                result.append((sub, True))
        else:
            result.append((item, False))
    return result


@dataclass
class MenuComponent(Component):
    """Dynamic navigation menu with optional two-level grouping.

    Flat items navigate directly. Group items (those with sub-items) render as
    non-clickable section headers followed by indented child buttons.
    """

    items: list[MenuItem]
    orientation: str = "vertical"
    page_id_map: dict[str, str] = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)

    def _color(self, *keys: str, fallback_id: int, fallback_percent: float = 0.0) -> dict:
        d = self.tokens
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return _theme_color(fallback_id, fallback_percent)
            d = d[key]
        if isinstance(d, str):
            return _hex_color(d)
        return _theme_color(fallback_id, fallback_percent)

    def _token_str(self, *keys: str) -> str | None:
        d = self.tokens
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return None
            d = d[key]
        return d if isinstance(d, str) else None

    def _token_int(self, *keys: str, default: int = 0) -> int:
        d = self.tokens
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return default
            d = d[key]
        return int(d) if isinstance(d, (int, float)) else default

    def _effective_cell(self, cell: Cell, n_items: int) -> Cell:
        """Return a cell whose height is capped to n_items × item_height when the
        token is set, otherwise use the full cell height (legacy stretch behaviour)."""
        item_h = self._token_int("menu", "item_height", default=0)
        if item_h > 0:
            natural_h = round(item_h * n_items, 4)
            if natural_h < cell.height:
                return Cell(x=cell.x, y=cell.y, width=cell.width, height=natural_h, z=cell.z)
        return cell

    def resolve(self, cell: Cell) -> list[Visual]:
        flat = _flatten(self.items)
        n = len(flat)
        if n == 0:
            return []

        cell = self._effective_cell(cell, n)
        visuals: list[Visual] = []

        # Background panel behind all items
        bg_color = self._token_str("menu", "background_color")
        if bg_color:
            visuals.append(self._make_background(cell, bg_color))

        for slot, (item, is_child) in enumerate(flat):
            item_cell = self._slot_cell(cell, slot, n, is_child)
            if item.is_group:
                visuals.append(self._make_header(item, item_cell, slot))
            else:
                visuals.append(self._make_button(item, item_cell, slot, is_child))
        return visuals

    def _make_background(self, cell: Cell, color: str) -> Visual:
        """White/colored background panel behind all menu items."""
        config: dict = {
            "objects": {
                "fill": [
                    {
                        "properties": {
                            "show": _literal("true"),
                            "fillColor": _hex_color(color),
                            "transparency": _literal("0D"),
                        }
                    },
                    {
                        "properties": {"fillColor": _hex_color(color)},
                        "selector": {"id": "default"},
                    },
                ],
                "shape": [{"properties": {"tileShape": _literal("'rectangle'")}}],
                "rotation": [{"properties": {"shapeAngle": _literal("0L")}}],
                "outline": [{"properties": {"show": _literal("false")}}],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": _literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        }
        vid = _make_id(f"menu-bg-{cell.z}")
        return Visual(
            name=vid,
            visual_type="shape",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z - 1,
                width=cell.width, height=cell.height,
                tab_order=cell.z - 1,
            ),
            config=config,
        )

    def _slot_cell(self, cell: Cell, slot: int, total: int, is_child: bool) -> Cell:
        if self.orientation == "vertical":
            item_h = cell.height / total
            indent = _CHILD_INDENT if is_child else 0.0
            return Cell(
                x=cell.x + indent,
                y=round(cell.y + slot * item_h, 4),
                width=cell.width - indent,
                height=round(item_h, 4),
                z=cell.z + slot * 100,
            )
        # horizontal — no indent concept
        item_w = cell.width / total
        return Cell(
            x=round(cell.x + slot * item_w, 4),
            y=cell.y,
            width=round(item_w, 4),
            height=cell.height,
            z=cell.z + slot * 100,
        )

    def _make_header(self, item: MenuItem, cell: Cell, slot: int) -> Visual:
        """Non-navigating section header with optional background fill."""
        header_bg = self._token_str("menu", "header", "background_color")

        fill_entries: list[dict] = []
        if header_bg:
            fill_entries.append({
                "properties": {
                    "show": _literal("true"),
                    "fillColor": _hex_color(header_bg),
                    "transparency": _literal("0D"),
                }
            })
        else:
            fill_entries.append({"properties": {"show": _literal("false")}})

        objects: dict = {
            "text": [
                {"properties": {"show": _literal("true")}},
                {
                    "properties": {
                        "text": _literal(f"'{item.page}'"),
                        "fontColor": self._color("menu", "header", "font_color", fallback_id=1, fallback_percent=0),
                        "verticalAlignment": _literal("'middle'"),
                        "horizontalAlignment": _literal("'left'"),
                        "fontSize": _literal("10D"),
                        "fontFamily": _literal(
                            "'''Segoe UI Bold'', wf_segoe-ui_bold, helvetica, arial, sans-serif'"
                        ),
                        "leftMargin": _literal("7L"),
                    },
                    "selector": {"id": "default"},
                },
            ],
            "fill": fill_entries,
            "outline": [{"properties": {"show": _literal("false")}}],
            "icon": [{"properties": {"show": _literal("false")}}],
        }

        container_objects: dict = {
            "visualLink": [{
                "properties": {
                    "show": _literal("false"),
                    "type": _literal("'PageNavigation'"),
                }
            }],
            "visualHeader": [{"properties": {"show": _literal("false")}}],
        }

        config: dict = {
            "objects": objects,
            "visualContainerObjects": container_objects,
        }

        vid = _make_id(f"menu-header-{item.page}-{cell.z}-{slot}")
        return Visual(
            name=vid,
            visual_type="actionButton",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height,
                tab_order=cell.z,
            ),
            config=config,
        )

    def _button_fill(self, is_child: bool) -> list[dict]:
        """Build fill entries for an actionButton.

        Child items get a default fill from fill_color_default token (submenu
        background, e.g. #f8f8f8). All items share the hover (84% transparent)
        and selected (solid) fill states.
        """
        default_fill_color = self._token_str("menu", "item", "fill_color_default") if is_child else None
        if default_fill_color:
            base = [{
                "properties": {
                    "show": _literal("true"),
                    "fillColor": _hex_color(default_fill_color),
                    "transparency": _literal("0D"),
                }
            }]
        else:
            base = [{"properties": {"show": _literal("false")}}]

        return base + [
            {
                "properties": {
                    "fillColor": self._color("menu", "item", "fill_color_hover", fallback_id=3, fallback_percent=0.4),
                    "transparency": _literal("84D"),
                },
                "selector": {"id": "hover"},
            },
            {
                "properties": {
                    "fillColor": self._color("menu", "item", "fill_color_selected", fallback_id=3, fallback_percent=0),
                    "transparency": _literal("0D"),
                },
                "selector": {"id": "selected"},
            },
        ]

    def _make_button(self, item: MenuItem, cell: Cell, index: int, is_child: bool = False) -> Visual:
        page_id = self.page_id_map.get(item.page, "")

        objects: dict = {
            "icon": [
                {
                    "properties": {"shapeType": _literal("'blank'")},
                    "selector": {"id": "default"},
                },
                {"properties": {"show": _literal("false")}},
            ],
            "outline": [
                {"properties": {"show": _literal("false")}},
                {
                    "properties": {
                        "lineColor": self._color("menu", "item", "outline_color", fallback_id=8, fallback_percent=0),
                        "weight": _literal("5D"),
                    },
                    "selector": {"id": "default"},
                },
            ],
            "text": [
                {"properties": {"show": _literal("true")}},
                {
                    "properties": {
                        "text": _literal(f"'{item.page}'"),
                        "fontColor": self._color("menu", "item", "font_color_default", fallback_id=3, fallback_percent=0.2),
                        "verticalAlignment": _literal("'middle'"),
                        "horizontalAlignment": _literal("'left'"),
                        "fontSize": _literal("10D"),
                        "fontFamily": _literal(
                            "'''Segoe UI Bold'', wf_segoe-ui_bold, helvetica, arial, sans-serif'"
                        ),
                        "leftMargin": _literal("7L"),
                    },
                    "selector": {"id": "default"},
                },
                {
                    "properties": {"fontColor": self._color("menu", "item", "font_color_hover", fallback_id=3, fallback_percent=0.4)},
                    "selector": {"id": "hover"},
                },
                {
                    "properties": {"fontColor": self._color("menu", "item", "font_color_selected", fallback_id=3, fallback_percent=0)},
                    "selector": {"id": "selected"},
                },
            ],
            "fill": self._button_fill(is_child),
        }

        general_props: dict = {"keepLayerOrder": _literal("true")}
        if item.description:
            general_props["altText"] = _literal(f"'{item.description}'")

        visual_link_props: dict = {
            "show": _literal("true"),
            "type": _literal("'PageNavigation'"),
            "navigationSection": _literal(f"'{page_id}'"),
        }
        if item.description:
            visual_link_props["tooltip"] = _literal(f"'{item.description}'")

        container_objects: dict = {
            "dropShadow": [{
                "properties": {
                    "show": _literal("false"),
                    "preset": _literal("'Custom'"),
                    "position": _literal("'Inner'"),
                    "color": self._color("menu", "item", "fill_color_selected", fallback_id=3, fallback_percent=0),
                    "transparency": _literal("0D"),
                    "shadowSpread": _literal("0D"),
                    "shadowBlur": _literal("0D"),
                    "angle": _literal("90D"),
                    "shadowDistance": _literal("3D"),
                }
            }],
            "title": [{
                "properties": {
                    "text": _literal(f"'{item.page}'"),
                    "titleWrap": _literal("true"),
                }
            }],
            "background": [{
                "properties": {
                    "show": _literal("false"),
                    "transparency": _literal("0D"),
                }
            }],
            "general": [{"properties": general_props}],
            "border": [{"properties": {"show": _literal("false")}}],
            "visualHeader": [{"properties": {"show": _literal("false")}}],
            "visualLink": [{"properties": visual_link_props}],
        }

        config: dict = {
            "objects": objects,
            "visualContainerObjects": container_objects,
            "drillFilterOtherVisuals": True,
        }

        vid = _make_id(f"menu-{item.page}-{cell.z}-{index}")
        return Visual(
            name=vid,
            visual_type="actionButton",
            position=Position(
                x=cell.x,
                y=cell.y,
                z=cell.z,
                width=cell.width,
                height=cell.height,
                tab_order=cell.z,
            ),
            config=config,
        )
