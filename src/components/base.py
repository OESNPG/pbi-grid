from abc import ABC, abstractmethod

from ..grid.schema import Cell
from ..models import Visual


class Component(ABC):
    """Base interface for all pbi-grid components.

    A component receives a resolved Cell (position + dimensions computed by the
    engine) and returns one or more Visual objects ready for PBIR serialization.
    """

    @abstractmethod
    def resolve(self, cell: Cell) -> list[Visual]:
        ...
