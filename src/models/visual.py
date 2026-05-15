import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .position import Position

_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"


@dataclass
class Visual:
    name: str
    visual_type: str
    position: Position
    config: dict = field(default_factory=dict)
    filter_config: dict = field(default_factory=dict)
    raw_data: dict[str, Any] | None = None  # full PBIR JSON when loaded from existing report

    def to_dict(self) -> dict:
        if self.raw_data is not None:
            # Preserve all existing visual data; only update position.
            result = dict(self.raw_data)
            result["position"] = self.position.to_dict()
            return result
        d: dict = {
            "$schema": _SCHEMA,
            "name": self.name,
            "position": self.position.to_dict(),
            "visual": {
                "visualType": self.visual_type,
                **self.config,
            },
        }
        if self.filter_config:
            d["filterConfig"] = self.filter_config
        return d

    def to_pbir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "visual.json").write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def from_pbir(cls, path: Path) -> "Visual":
        data = json.loads((path / "visual.json").read_text(encoding="utf-8"))
        visual_block = dict(data.get("visual", {}))
        visual_type = visual_block.pop("visualType", "")
        return cls(
            name=data["name"],
            visual_type=visual_type,
            position=Position.from_dict(data["position"]),
            config=visual_block,
            filter_config=data.get("filterConfig", {}),
            raw_data=data,
        )
