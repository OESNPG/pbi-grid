from pathlib import Path

from .base import Component
from .header import HeaderComponent
from .menu import MenuComponent, MenuItem
from .footer import FooterComponent, FooterLink, FooterLinkGroup

_REGISTRY: dict[str, type[Component]] = {
    "header": HeaderComponent,
    "menu": MenuComponent,
    "footer": FooterComponent,
}

DEFAULT_HEIGHTS: dict[str, int] = {
    "header": 64,
    "footer": 232,
    "menu": 424,
}

DEFAULT_SPANS: dict[str, int] = {
    "header": 12,
    "footer": 12,
    "menu": 2,
}


def _parse_menu_items(raw: list[dict]) -> list[MenuItem]:
    items = []
    for i in raw:
        if i.get("separator"):
            items.append(MenuItem(is_separator=True))
            continue
        sub_raw = i.get("items", [])
        items.append(MenuItem(
            page=i.get("page", ""),
            description=i.get("description", ""),
            icon=i.get("icon", ""),
            items=_parse_menu_items(sub_raw) if sub_raw else [],
        ))
    return items


def resolve_component(
    name: str,
    props: dict,
    page_id_map: dict[str, str],
    tokens: dict | None = None,
    theme_dir: Path | None = None,
) -> Component:
    """Instantiate a component by name, passing layout props, page map and design tokens."""
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown component '{name}'. Available: {list(_REGISTRY)}"
        )
    cls = _REGISTRY[name]

    if cls is HeaderComponent:
        return HeaderComponent(
            title=props.get("title", ""),
            subtitle=props.get("subtitle", ""),
            tokens=tokens or {},
            theme_dir=theme_dir,
            logo_path=props.get("logo_path", ""),
            logo_width=int(props.get("logo_width", 0)),
            logo_height=int(props.get("logo_height", 0)),
            logo_align=props.get("logo_align", ""),
            logo_alt_text=props.get("logo_alt_text", ""),
        )

    if cls is MenuComponent:
        items = _parse_menu_items(props.get("items", []))
        return MenuComponent(
            items=items,
            orientation=props.get("orientation", "vertical"),
            page_id_map=page_id_map,
            tokens=tokens or {},
            theme_dir=theme_dir,
        )

    if cls is FooterComponent:
        raw_links = props.get("links", [])
        link_groups = [
            FooterLinkGroup(
                title=g.get("title", ""),
                items=[FooterLink(label=i["label"], url=i.get("url", "")) for i in g.get("items", [])],
            )
            for g in raw_links
        ]
        return FooterComponent(
            legal=props.get("legal", ""),
            links=link_groups,
            tokens=tokens or {},
            theme_dir=theme_dir,
            logo_path=props.get("logo_path", ""),
            logo_height=int(props.get("logo_height", 0)),
            logo_alt_text=props.get("logo_alt_text", ""),
        )

    raise ValueError(f"No factory defined for component '{name}'")


def _collect_menu_icons(item: dict, candidates: list[str]) -> None:
    """Recursively collect icon filenames from a raw menu item dict."""
    icon = item.get("icon", "")
    if icon:
        candidates.append(icon)
    for sub in item.get("items", []):
        _collect_menu_icons(sub, candidates)


__all__ = [
    "Component",
    "HeaderComponent",
    "MenuComponent", "MenuItem",
    "FooterComponent", "FooterLink", "FooterLinkGroup",
    "resolve_component",
    "_collect_menu_icons",
]
