from abc import ABC, abstractmethod

from ..grid.schema import Cell
from ..models import Visual


class TokenMixin:
    """Typed token-lookup helpers for component classes.

    Expects ``self.tokens`` to be a dict loaded from the active theme's
    ``tokens.yaml``. All methods are safe to call when the dict is empty or
    when a requested key path does not exist.
    """

    tokens: dict  # declared by the concrete dataclass subclass

    def _token_str(self, *keys: str) -> str | None:
        """Return a string value at the given dot-path keys, or None."""
        d = self.tokens
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return None
            d = d[key]
        return d if isinstance(d, str) else None

    def _token_int(self, *keys: str, default: int = 0) -> int:
        """Return an int value at the given dot-path keys, or *default*."""
        d = self.tokens
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return default
            d = d[key]
        return int(d) if isinstance(d, (int, float)) else default


class Component(ABC):
    """Base interface for all pbi-grid components.

    A component receives a resolved Cell (position + dimensions computed by the
    engine) and returns one or more Visual objects ready for PBIR serialization.
    """

    @abstractmethod
    def resolve(self, cell: Cell) -> list[Visual]:
        """Translate a grid Cell into one or more PBIR Visual objects."""
