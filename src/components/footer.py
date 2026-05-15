import hashlib
from dataclasses import dataclass, field
from pathlib import Path

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
class FooterLink:
    label: str
    url: str = ""


@dataclass
class FooterLinkGroup:
    title: str
    items: list[FooterLink] = field(default_factory=list)


@dataclass
class FooterComponent(Component):
    """GovBR-styled footer bar.

    Renders a background rectangle, optional logo (top-left), optional site-map
    link columns (web URL navigation), a horizontal divider above the legal bar,
    and a legal text strip at the bottom.
    """

    legal: str = ""
    links: list[FooterLinkGroup] = field(default_factory=list)
    tokens: dict = field(default_factory=dict)
    theme_dir: Path | None = None  # resolved by __init__.py from packages.theme_dir()
    logo_path: str = ""            # overrides tokens footer.logo_path when set
    logo_height: int = 0           # overrides tokens footer.logo_height when > 0

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
        visuals: list[Visual] = []

        bg_color = self._token_str("footer", "background_color") or "#071D41"
        divider_color = self._token_str("footer", "divider_color")
        divider_h = self._token_int("footer", "divider_height", default=0)
        legal_h = self._token_int("footer", "legal_height", default=44) if self.legal else 0
        logo_h = self._logo_reserved_height()

        # Full background
        visuals.append(self._make_shape(
            _make_id(f"footer-bg-{cell.z}"),
            cell, bg_color, cell.z - 1,
        ))

        # Top divider stripe
        if divider_color and divider_h > 0:
            div_cell = Cell(
                x=cell.x, y=cell.y,
                width=cell.width, height=divider_h,
                z=cell.z,
            )
            visuals.append(self._make_shape(
                _make_id(f"footer-div-{cell.z}"),
                div_cell, divider_color, cell.z,
            ))

        # Logo row — own dedicated line, top-left, logo_height tall
        if logo_h > 0:
            logo_w = self._token_int("footer", "logo_width", default=165)
            logo_cell = Cell(
                x=cell.x, y=round(cell.y + divider_h, 4),
                width=float(logo_w), height=float(logo_h),
                z=cell.z + 1,
            )
            logo_visual = self._make_logo(logo_cell)
            if logo_visual:
                visuals.append(logo_visual)

        # Link columns — below the logo row, full width
        content_y = round(cell.y + divider_h + logo_h, 4)
        content_h = cell.height - divider_h - logo_h - legal_h
        if self.links and content_h > 0:
            visuals.extend(
                self._make_link_columns(cell.x, content_y, cell.width, content_h, cell.z)
            )

        # Legal bar — thin divider line + text
        if self.legal and legal_h > 0:
            legal_y = cell.y + cell.height - legal_h

            # 1px separator above legal text
            if divider_color:
                sep_cell = Cell(
                    x=cell.x, y=legal_y,
                    width=cell.width, height=1,
                    z=cell.z + 900,
                )
                visuals.append(self._make_shape(
                    _make_id(f"footer-sep-{cell.z}"),
                    sep_cell, divider_color, cell.z + 900,
                ))

            legal_cell = Cell(
                x=cell.x, y=legal_y + (1 if divider_color else 0),
                width=cell.width, height=legal_h - (1 if divider_color else 0),
                z=cell.z + 901,
            )
            visuals.append(self._make_legal(legal_cell))

        return visuals

    def _effective_logo_path(self) -> str:
        return self.logo_path or self._token_str("footer", "logo_path") or ""

    def _logo_reserved_height(self) -> int:
        """Height reserved for the logo area (0 when no logo is configured)."""
        logo_path = self._effective_logo_path()
        if not logo_path or not self.theme_dir:
            return 0
        if not (self.theme_dir / logo_path).exists():
            return 0
        if self.logo_height > 0:
            return self.logo_height
        return self._token_int("footer", "logo_height", default=60)

    def _make_logo(self, cell: Cell) -> Visual | None:
        logo_path = self._effective_logo_path()
        if not logo_path or not self.theme_dir:
            return None
        item_name = Path(logo_path).name
        config: dict = {
            "objects": {
                "general": [
                    {
                        "properties": {
                            "imageUrl": {
                                "expr": {
                                    "ResourcePackageItem": {
                                        "PackageName": "RegisteredResources",
                                        "PackageType": 1,
                                        "ItemName": item_name,
                                    }
                                }
                            },
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "title": [{"properties": {"show": _literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        }
        return Visual(
            name=_make_id(f"footer-logo-{cell.z}"),
            visual_type="image",
            position=Position(
                x=cell.x, y=cell.y, z=cell.z,
                width=cell.width, height=cell.height,
                tab_order=cell.z,
            ),
            config=config,
        )

    # ------------------------------------------------------------------
    # Link columns
    # ------------------------------------------------------------------

    def _make_link_columns(
        self, x: float, y: float, width: float, height: float, base_z: int
    ) -> list[Visual]:
        visuals: list[Visual] = []
        n = len(self.links)
        if n == 0:
            return visuals

        col_w = width / n
        item_h = self._token_int("footer", "item_height", default=24)
        title_color = self._token_str("footer", "title_color") or "#FFFFFF"
        link_color = self._token_str("footer", "link_color") or "#C9D4E3"
        title_size = self._token_int("footer", "title_font_size", default=10)
        link_size = self._token_int("footer", "link_font_size", default=9)

        for col_idx, group in enumerate(self.links):
            cx = round(x + col_idx * col_w, 4)
            z_col = base_z + col_idx * 20

            # Column title
            title_cell = Cell(
                x=cx, y=round(y, 4),
                width=round(col_w, 4), height=item_h,
                z=z_col + 1,
            )
            visuals.append(self._make_button(
                _make_id(f"footer-t-{col_idx}-{base_z}"),
                group.title, title_cell, title_color, title_size, bold=True, url="",
            ))

            # Column items
            for row_idx, link in enumerate(group.items):
                item_y = round(y + item_h * (row_idx + 1), 4)
                if item_y + item_h > y + height:
                    break
                item_cell = Cell(
                    x=cx, y=item_y,
                    width=round(col_w, 4), height=item_h,
                    z=z_col + 2 + row_idx,
                )
                visuals.append(self._make_button(
                    _make_id(f"footer-l-{col_idx}-{row_idx}-{base_z}"),
                    link.label, item_cell, link_color, link_size, bold=False, url=link.url,
                ))

        return visuals

    # ------------------------------------------------------------------
    # Visual factories
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
        if url:
            link_props: dict = {
                "show": _literal("true"),
                "type": _literal("'WebUrl'"),
                "webUrl": _literal(f"'{url}'"),
            }
        else:
            link_props = {"show": _literal("false")}

        config: dict = {
            "objects": {
                "icon": [{"properties": {"show": _literal("false")}}],
                "outline": [{"properties": {"show": _literal("false")}}],
                "fill": [{"properties": {"show": _literal("false")}}],
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
                            "leftMargin": _literal("8L"),
                            "bold": _literal("true" if bold else "false"),
                        },
                        "selector": {"id": "default"},
                    },
                ],
            },
            "visualContainerObjects": {
                "visualLink": [{"properties": link_props}],
                "visualHeader": [{"properties": {"show": _literal("false")}}],
                "background": [{"properties": {"show": _literal("false")}}],
                "border": [{"properties": {"show": _literal("false")}}],
            },
            "drillFilterOtherVisuals": True,
        }
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

    def _make_legal(self, cell: Cell) -> Visual:
        color = self._token_str("footer", "legal_color") or "#A8B5C3"
        size = self._token_int("footer", "legal_font_size", default=9)
        return self._make_button(
            _make_id(f"footer-legal-{cell.z}"),
            self.legal, cell, color, size, bold=False, url="",
        )

    def _make_shape(self, vid: str, cell: Cell, color: str, z: int) -> Visual:
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
        return Visual(
            name=vid,
            visual_type="shape",
            position=Position(
                x=cell.x, y=cell.y, z=z,
                width=cell.width, height=cell.height,
                tab_order=z,
            ),
            config=config,
        )
