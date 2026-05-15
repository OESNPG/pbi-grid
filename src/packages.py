from pathlib import Path

import yaml

_THEMES_ROOT = Path(__file__).parent.parent / "themes"


def load_tokens(package: str | None) -> dict:
    """Load tokens.yaml from themes/{package}/tokens.yaml."""
    if not package:
        return {}
    tokens_path = _THEMES_ROOT / package / "tokens.yaml"
    if not tokens_path.exists():
        return {}
    return yaml.safe_load(tokens_path.read_text(encoding="utf-8")) or {}


def theme_dir(package: str | None) -> Path | None:
    """Return the theme directory for the given package name, or None."""
    if not package:
        return None
    d = _THEMES_ROOT / package
    return d if d.is_dir() else None
