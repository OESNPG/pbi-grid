from dataclasses import dataclass


@dataclass
class Position:
    x: float
    y: float
    z: int
    width: float
    height: float
    tab_order: int

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "height": self.height,
            "width": self.width,
            "tabOrder": self.tab_order,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(
            x=data["x"],
            y=data["y"],
            z=data["z"],
            width=data["width"],
            height=data["height"],
            tab_order=data["tabOrder"],
        )
