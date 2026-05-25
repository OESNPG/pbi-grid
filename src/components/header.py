from dataclasses import dataclass, field
from pathlib import Path

from .base import Component, TokenMixin
from ..grid.schema import Cell
from ..models import Visual, Position
from ..pbir_utils import make_id, literal, hex_color

_FONT_FAMILY = "'''Rawline'', ''Raleway'', wf_standard-font, helvetica, arial, sans-serif'"
_LOGO_PADDING = 8.0  # px gap between logo and cell/text edge


@dataclass
class HeaderComponent(TokenMixin, Component):
    """GovBR-styled header bar.

    Renders a background rectangle, a title text button, an optional subtitle,
    an optional logo image, and an optional accent stripe at the bottom.
    """

    title: str
    subtitle: str = ""
    tokens: dict = field(default_factory=dict)
    theme_dir: Path | None = None
    logo_path: str = ""       # filename relative to theme dir; overrides token
    logo_width: int = 0       # px; 0 → use token default (80)
    logo_height: int = 0      # px; 0 → use token default (40)
    logo_align: str = ""      # "left" | "right"; "" → use token default ("left")
    logo_alt_text: str = ""

    def resolve(self, cell: Cell) -> list[Visual]:
        """Render the header into background, text, optional logo, and accent bar visuals."""
        accent_height = self._token_int("header", "accent_height", default=0)
        content_height = cell.height - accent_height

        visuals: list[Visual] = [self._make_background(cell)]

        logo_visual, text_x, text_w = self._resolve_logo(cell, content_height)
        if logo_visual:
            visuals.append(logo_visual)

        if self.subtitle:
            half = content_height / 2
            visuals.append(self._make_text(self.title, Cell(
                x=text_x, y=cell.y, width=text_w, height=half, z=cell.z + 1,
            ), "title"))
            visuals.append(self._make_text(self.subtitle, Cell(
                x=text_x, y=round(cell.y + half, 4), width=text_w, height=half, z=cell.z + 2,
            ), "subtitle"))
        else:
            visuals.append(self._make_text(self.title, Cell(
                x=text_x, y=cell.y, width=text_w, height=content_height, z=cell.z + 1,
            ), "title"))

        accent_color = self._token_str("header", "accent_color")
        if accent_color and accent_height > 0:
            accent_cell = Cell(
                x=cell.x, y=round(cell.y + content_height, 4),
                width=cell.width, height=accent_height, z=cell.z + 10,
            )
            visuals.append(self._make_accent_bar(accent_cell, accent_color))

        return visuals

    # ------------------------------------------------------------------
    # Logo
    # ------------------------------------------------------------------

    def _effective_logo_path(self) -> str:
        return self.logo_path or self._token_str("header", "logo_path") or ""

    def _resolve_logo(
        self, cell: Cell, content_height: float
    ) -> tuple["Visual | None", float, float]:
        """Return (logo_visual, text_x, text_width).

        When no logo is configured, text_x == cell.x and text_width == cell.width.
        """
        logo_path = self._effective_logo_path()
        if not logo_path or not self.theme_dir:
            return None, cell.x, cell.width

        logo_file = self.theme_dir / logo_path
        if not logo_file.exists():
            return None, cell.x, cell.width

        logo_w = float(self.logo_width or self._token_int("header", "logo_width", default=80))
        logo_h = float(self.logo_height or self._token_int("header", "logo_height", default=40))
        logo_align = self.logo_align or self._token_str("header", "logo_align") or "left"
        logo_h = min(logo_h, content_height - 2 * _LOGO_PADDING)
        logo_y = round(cell.y + (content_height - logo_h) / 2, 4)

        if logo_align == "right":
            logo_x = round(cell.x + cell.width - logo_w - _LOGO_PADDING, 4)
            text_x, text_w = cell.x, round(cell.width - logo_w - 2 * _LOGO_PADDING, 4)
        else:
            logo_x = round(cell.x + _LOGO_PADDING, 4)
            text_x = round(cell.x + logo_w + 2 * _LOGO_PADDING, 4)
            text_w = round(cell.width - logo_w - 3 * _LOGO_PADDING, 4)

        item_name = Path(logo_path).name
        alt_text = self.logo_alt_text or self._token_str("header", "logo_alt_text") or ""
        general_props: dict = {
            "imageUrl": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources",
                "PackageType": 1,
                "ItemName": item_name,
            }}}
        }
        if alt_text:
            general_props["altText"] = literal(f"'{alt_text}'")

        logo_visual = Visual(
            name=make_id(f"header-logo-{cell.z}"),
            visual_type="image",
            position=Position(
                x=logo_x, y=logo_y, z=cell.z + 5,
                width=logo_w, height=logo_h, tab_order=cell.z + 5,
            ),
            config={
                "objects": {"general": [{"properties": general_props}]},
                "visualContainerObjects": {
                    "title": [{"properties": {"show": literal("false")}}],
                },
                "drillFilterOtherVisuals": True,
            },
        )
        return logo_visual, text_x, text_w

    # ------------------------------------------------------------------
    # Visual builders
    # ------------------------------------------------------------------

    def _make_background(self, cell: Cell) -> Visual:
        """Solid filled rectangle covering the full header cell."""
        bg_color = self._token_str("header", "background_color") or "#FFFFFF"
        return Visual(
            name=make_id(f"header-bg-{cell.z}"),
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
                            "fillColor": hex_color(bg_color),
                            "transparency": literal("0D"),
                        }},
                        {"properties": {"fillColor": hex_color(bg_color)}, "selector": {"id": "default"}},
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

    def _make_text(self, text: str, cell: Cell, role: str) -> Visual:
        """Action button used to render title or subtitle text."""
        color = self._token_str("header", f"{role}_color") or "#FFFFFF"
        size = self._token_int("header", f"{role}_font_size", default=14 if role == "title" else 10)
        return Visual(
            name=make_id(f"header-{role}-{cell.z}"),
            visual_type="actionButton",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height, tab_order=cell.z,
            ),
            config={
                "objects": {
                    "icon": [{"properties": {"show": literal("false")}}],
                    "outline": [{"properties": {"show": literal("false")}}],
                    "text": [
                        {"properties": {"show": literal("true")}},
                        {"properties": {
                            "text": literal(f"'{text}'"),
                            "fontColor": hex_color(color),
                            "verticalAlignment": literal("'middle'"),
                            "horizontalAlignment": literal("'left'"),
                            "fontSize": literal(f"{size}D"),
                            "fontFamily": literal(_FONT_FAMILY),
                            "leftMargin": literal("16L"),
                            "bold": literal("true"),
                        }, "selector": {"id": "default"}},
                    ],
                    "fill": [{"properties": {"show": literal("false")}}],
                },
                "visualContainerObjects": {
                    "visualLink": [{"properties": {
                        "show": literal("false"),
                        "type": literal("'PageNavigation'"),
                    }}],
                    "visualHeader": [{"properties": {"show": literal("false")}}],
                    "background": [{"properties": {"show": literal("false"), "transparency": literal("0D")}}],
                    "border": [{"properties": {"show": literal("false")}}],
                },
                "drillFilterOtherVisuals": True,
            },
        )

    def _make_accent_bar(self, cell: Cell, color: str) -> Visual:
        """Thin filled rectangle rendered as a bottom accent stripe."""
        return Visual(
            name=make_id(f"header-accent-{cell.z}"),
            visual_type="shape",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height, tab_order=cell.z,
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
            },
        )
