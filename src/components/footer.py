from dataclasses import dataclass, field
from pathlib import Path

from .base import Component, TokenMixin
from ..grid.schema import Cell
from ..models import Visual, Position
from ..pbir_utils import make_id, literal, hex_color


@dataclass
class FooterLink:
    label: str
    url: str = ""


@dataclass
class FooterLinkGroup:
    title: str
    items: list[FooterLink] = field(default_factory=list)


@dataclass
class FooterComponent(TokenMixin, Component):
    """Footer bar with optional logo, link columns, and legal text strip.

    Renders: background rectangle → top divider stripe → logo image →
    sitemap link columns → horizontal separator → legal text.
    """

    legal: str = ""
    links: list[FooterLinkGroup] = field(default_factory=list)
    tokens: dict = field(default_factory=dict)
    theme_dir: Path | None = None
    logo_path: str = ""       # overrides tokens footer.logo_path when set
    logo_height: int = 0      # overrides tokens footer.logo_height when > 0
    logo_alt_text: str = ""   # overrides tokens footer.logo_alt_text when set

    def resolve(self, cell: Cell) -> list[Visual]:
        """Render the footer into its constituent PBIR visuals."""
        visuals: list[Visual] = []

        bg_color = self._token_str("footer", "background_color") or "#071D41"
        divider_color = self._token_str("footer", "divider_color")
        divider_h = self._token_int("footer", "divider_height", default=0)
        legal_h = self._token_int("footer", "legal_height", default=44) if self.legal else 0
        logo_h = self._logo_reserved_height()

        visuals.append(self._make_shape(make_id(f"footer-bg-{cell.z}"), cell, bg_color, cell.z - 1))

        if divider_color and divider_h > 0:
            visuals.append(self._make_shape(
                make_id(f"footer-div-{cell.z}"),
                Cell(x=cell.x, y=cell.y, width=cell.width, height=divider_h, z=cell.z),
                divider_color, cell.z,
            ))

        if logo_h > 0:
            logo_w = self._token_int("footer", "logo_width", default=165)
            logo_visual = self._make_logo(Cell(
                x=cell.x, y=round(cell.y + divider_h, 4),
                width=float(logo_w), height=float(logo_h), z=cell.z + 1,
            ))
            if logo_visual:
                visuals.append(logo_visual)

        content_y = round(cell.y + divider_h + logo_h, 4)
        content_h = cell.height - divider_h - logo_h - legal_h
        if self.links and content_h > 0:
            visuals.extend(self._make_link_columns(cell.x, content_y, cell.width, content_h, cell.z))

        if self.legal and legal_h > 0:
            legal_y = cell.y + cell.height - legal_h
            if divider_color:
                visuals.append(self._make_shape(
                    make_id(f"footer-sep-{cell.z}"),
                    Cell(x=cell.x, y=legal_y, width=cell.width, height=1, z=cell.z + 900),
                    divider_color, cell.z + 900,
                ))
            legal_cell = Cell(
                x=cell.x, y=legal_y + (1 if divider_color else 0),
                width=cell.width, height=legal_h - (1 if divider_color else 0),
                z=cell.z + 901,
            )
            visuals.append(self._make_legal(legal_cell))

        return visuals

    # ------------------------------------------------------------------
    # Logo
    # ------------------------------------------------------------------

    def _effective_logo_path(self) -> str:
        return self.logo_path or self._token_str("footer", "logo_path") or ""

    def _logo_reserved_height(self) -> int:
        """Height reserved for the logo row; 0 when no logo file is resolvable."""
        logo_path = self._effective_logo_path()
        if not logo_path or not self.theme_dir:
            return 0
        if not (self.theme_dir / logo_path).exists():
            return 0
        if self.logo_height > 0:
            return self.logo_height
        return self._token_int("footer", "logo_height", default=60)

    def _effective_logo_alt_text(self) -> str:
        return self.logo_alt_text or self._token_str("footer", "logo_alt_text") or ""

    def _make_logo(self, cell: Cell) -> Visual | None:
        """Image visual for the footer logo; None when the logo file is not found."""
        logo_path = self._effective_logo_path()
        if not logo_path or not self.theme_dir:
            return None
        item_name = Path(logo_path).name
        alt_text = self._effective_logo_alt_text()
        general_props: dict = {
            "imageUrl": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources",
                "PackageType": 1,
                "ItemName": item_name,
            }}}
        }
        if alt_text:
            general_props["altText"] = literal(f"'{alt_text}'")
        return Visual(
            name=make_id(f"footer-logo-{cell.z}"),
            visual_type="image",
            position=Position(x=cell.x, y=cell.y, z=cell.z, width=cell.width, height=cell.height, tab_order=cell.z),
            config={
                "objects": {"general": [{"properties": general_props}]},
                "visualContainerObjects": {"title": [{"properties": {"show": literal("false")}}]},
                "drillFilterOtherVisuals": True,
            },
        )

    # ------------------------------------------------------------------
    # Link columns
    # ------------------------------------------------------------------

    def _make_link_columns(
        self, x: float, y: float, width: float, height: float, base_z: int
    ) -> list[Visual]:
        """Render all link groups as evenly-spaced columns of buttons."""
        if not self.links:
            return []

        n = len(self.links)
        col_w = width / n
        item_h = self._token_int("footer", "item_height", default=24)
        title_color = self._token_str("footer", "title_color") or "#FFFFFF"
        link_color = self._token_str("footer", "link_color") or "#C9D4E3"
        title_size = self._token_int("footer", "title_font_size", default=10)
        link_size = self._token_int("footer", "link_font_size", default=9)

        visuals: list[Visual] = []
        for col_idx, group in enumerate(self.links):
            cx = round(x + col_idx * col_w, 4)
            z_col = base_z + col_idx * 20
            visuals.append(self._make_button(
                make_id(f"footer-t-{col_idx}-{base_z}"),
                group.title,
                Cell(x=cx, y=round(y, 4), width=round(col_w, 4), height=item_h, z=z_col + 1),
                title_color, title_size, bold=True,
            ))
            for row_idx, link in enumerate(group.items):
                item_y = round(y + item_h * (row_idx + 1), 4)
                if item_y + item_h > y + height:
                    break
                visuals.append(self._make_button(
                    make_id(f"footer-l-{col_idx}-{row_idx}-{base_z}"),
                    link.label,
                    Cell(x=cx, y=item_y, width=round(col_w, 4), height=item_h, z=z_col + 2 + row_idx),
                    link_color, link_size, bold=False, url=link.url,
                ))
        return visuals

    # ------------------------------------------------------------------
    # Visual builders
    # ------------------------------------------------------------------

    def _make_button(
        self,
        vid: str,
        text: str,
        cell: Cell,
        color: str,
        size: int,
        bold: bool,
        url: str = "",
    ) -> Visual:
        """Action button for a footer link or title label."""
        link_props: dict = (
            {"show": literal("true"), "type": literal("'WebUrl'"), "webUrl": literal(f"'{url}'")}
            if url else
            {"show": literal("false")}
        )
        return Visual(
            name=vid,
            visual_type="actionButton",
            position=Position(x=cell.x, y=cell.y, z=cell.z, width=cell.width, height=cell.height, tab_order=cell.z),
            config={
                "objects": {
                    "icon": [{"properties": {"show": literal("false")}}],
                    "outline": [{"properties": {"show": literal("false")}}],
                    "fill": [{"properties": {"show": literal("false")}}],
                    "text": [
                        {"properties": {"show": literal("true")}},
                        {"properties": {
                            "text": literal(f"'{text}'"),
                            "fontColor": hex_color(color),
                            "verticalAlignment": literal("'middle'"),
                            "horizontalAlignment": literal("'left'"),
                            "fontSize": literal(f"{size}D"),
                            "fontFamily": literal(
                                "'''Rawline'', ''Raleway'', wf_standard-font, helvetica, arial, sans-serif'"
                            ),
                            "leftMargin": literal("8L"),
                            "bold": literal("true" if bold else "false"),
                        }, "selector": {"id": "default"}},
                    ],
                },
                "visualContainerObjects": {
                    "visualLink": [{"properties": link_props}],
                    "visualHeader": [{"properties": {"show": literal("false")}}],
                    "background": [{"properties": {"show": literal("false")}}],
                    "border": [{"properties": {"show": literal("false")}}],
                },
                "drillFilterOtherVisuals": True,
            },
        )

    def _make_legal(self, cell: Cell) -> Visual:
        """Small-text action button for the legal notice strip."""
        color = self._token_str("footer", "legal_color") or "#A8B5C3"
        size = self._token_int("footer", "legal_font_size", default=9)
        return self._make_button(make_id(f"footer-legal-{cell.z}"), self.legal, cell, color, size, bold=False)

    def _make_shape(self, vid: str, cell: Cell, color: str, z: int) -> Visual:
        """Solid filled rectangle (background, divider, or separator)."""
        return Visual(
            name=vid,
            visual_type="shape",
            position=Position(x=cell.x, y=cell.y, z=z, width=cell.width, height=cell.height, tab_order=z),
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
