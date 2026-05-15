import hashlib
from dataclasses import dataclass, field

from .base import Component
from ..grid.schema import Cell
from ..models import Visual, Position


def _make_id(seed: str) -> str:
    return hashlib.md5(seed.encode()).hexdigest()[:20]


def _literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _hex_color(hex_value: str) -> dict:
    return {
        "solid": {
            "color": {
                "expr": {
                    "Literal": {"Value": f"'{hex_value}'"}
                }
            }
        }
    }


_FONT_FAMILY = "'''Rawline'', ''Raleway'', wf_standard-font, helvetica, arial, sans-serif'"


@dataclass
class HeaderComponent(Component):
    """GovBR-styled header bar.

    Renders a background rectangle, a title text button, an optional subtitle,
    and an optional accent bar at the bottom (govbr yellow stripe).
    """

    title: str
    subtitle: str = ""
    tokens: dict = field(default_factory=dict)

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

    def resolve(self, cell: Cell) -> list[Visual]:
        accent_height = self._token_int("header", "accent_height", default=0)
        content_height = cell.height - accent_height

        visuals: list[Visual] = [self._make_background(cell)]

        if self.subtitle:
            half = content_height / 2
            title_cell = Cell(
                x=cell.x, y=cell.y,
                width=cell.width, height=half,
                z=cell.z + 1,
            )
            subtitle_cell = Cell(
                x=cell.x, y=round(cell.y + half, 4),
                width=cell.width, height=half,
                z=cell.z + 2,
            )
            visuals.append(self._make_text(self.title, title_cell, "title"))
            visuals.append(self._make_text(self.subtitle, subtitle_cell, "subtitle"))
        else:
            title_cell = Cell(
                x=cell.x, y=cell.y,
                width=cell.width, height=content_height,
                z=cell.z + 1,
            )
            visuals.append(self._make_text(self.title, title_cell, "title"))

        accent_color = self._token_str("header", "accent_color")
        if accent_color and accent_height > 0:
            accent_cell = Cell(
                x=cell.x, y=round(cell.y + content_height, 4),
                width=cell.width, height=accent_height,
                z=cell.z + 10,
            )
            visuals.append(self._make_accent_bar(accent_cell, accent_color))

        return visuals

    def _make_background(self, cell: Cell) -> Visual:
        bg_color = self._token_str("header", "background_color") or "#FFFFFF"
        config: dict = {
            "objects": {
                "fill": [
                    {"properties": {
                        "show": _literal("true"),
                        "fillColor": _hex_color(bg_color),
                        "transparency": _literal("0D"),
                    }},
                    {
                        "properties": {"fillColor": _hex_color(bg_color)},
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
        }
        vid = _make_id(f"header-bg-{cell.z}")
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

    def _make_text(self, text: str, cell: Cell, role: str) -> Visual:
        color = self._token_str("header", f"{role}_color") or "#FFFFFF"
        size = self._token_int("header", f"{role}_font_size", default=14 if role == "title" else 10)
        config: dict = {
            "objects": {
                "icon": [{"properties": {"show": _literal("false")}}],
                "outline": [{"properties": {"show": _literal("false")}}],
                "text": [
                    {"properties": {"show": _literal("true")}},
                    {
                        "properties": {
                            "text": _literal(f"'{text}'"),
                            "fontColor": _hex_color(color),
                            "verticalAlignment": _literal("'middle'"),
                            "horizontalAlignment": _literal("'left'"),
                            "fontSize": _literal(f"{size}D"),
                            "fontFamily": _literal(_FONT_FAMILY),
                            "leftMargin": _literal("16L"),
                            "bold": _literal("true"),
                        },
                        "selector": {"id": "default"},
                    },
                ],
                "fill": [{"properties": {"show": _literal("false")}}],
            },
            "visualContainerObjects": {
                "visualLink": [{"properties": {
                    "show": _literal("false"),
                    "type": _literal("'PageNavigation'"),
                }}],
                "visualHeader": [{"properties": {"show": _literal("false")}}],
                "background": [{"properties": {"show": _literal("false"), "transparency": _literal("0D")}}],
                "border": [{"properties": {"show": _literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        }
        vid = _make_id(f"header-{role}-{cell.z}")
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

    def _make_accent_bar(self, cell: Cell, color: str) -> Visual:
        config: dict = {
            "objects": {
                "fill": [
                    {"properties": {
                        "show": _literal("true"),
                        "fillColor": _hex_color(color),
                        "transparency": _literal("0D"),
                    }},
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
        }
        vid = _make_id(f"header-accent-{cell.z}")
        return Visual(
            name=vid,
            visual_type="shape",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height,
                tab_order=cell.z,
            ),
            config=config,
        )
