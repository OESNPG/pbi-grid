"""Shared low-level helpers for building Power BI PBIR JSON structures.

These utilities are intentionally kept as plain functions (no classes) so that
both the grid engine and all component renderers can import them without
introducing circular dependencies.
"""

import hashlib


def make_id(seed: str) -> str:
    """Return a deterministic 20-char hex ID suitable for a PBIR visual name.

    Real PBIR IDs are 20-char lowercase hex strings — when seed already matches
    that format it is returned unchanged. Otherwise a stable MD5-derived ID is
    generated, guaranteeing the same output for the same seed across runs.
    """
    if len(seed) == 20 and all(c in "0123456789abcdef" for c in seed):
        return seed
    return hashlib.md5(seed.encode()).hexdigest()[:20]


def literal(value: str) -> dict:
    """Wrap a raw DAX/M value string in the PBIR Literal expression envelope."""
    return {"expr": {"Literal": {"Value": value}}}


def hex_color(hex_value: str) -> dict:
    """Return a PBIR solid-color expression for a CSS hex string (e.g. '#1351B4')."""
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_value}'"}}}}}


def theme_color(color_id: int, percent: float) -> dict:
    """Return a PBIR ThemeDataColor expression used as a token-less palette fallback."""
    return {
        "solid": {
            "color": {
                "expr": {
                    "ThemeDataColor": {"ColorId": color_id, "Percent": percent}
                }
            }
        }
    }
