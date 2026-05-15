import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .visual import Visual

_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"


@dataclass
class Page:
    name: str
    display_name: str
    width: int = 1280
    height: int = 720
    display_option: str = "FitToPage"
    visuals: list[Visual] = field(default_factory=list)
    raw_page_data: dict[str, Any] | None = None  # full page.json when loaded from existing report

    def add_visual(self, visual: Visual) -> None:
        self.visuals.append(visual)

    def to_dict(self) -> dict:
        if self.raw_page_data is not None:
            # Preserve all existing page metadata (objects, visualInteractions, etc.);
            # only update the fields pbi-grid manages.
            result = dict(self.raw_page_data)
            result["name"] = self.name
            result["displayName"] = self.display_name
            result["displayOption"] = self.display_option
            result["height"] = self.height
            result["width"] = self.width
            return result
        return {
            "$schema": _SCHEMA,
            "name": self.name,
            "displayName": self.display_name,
            "displayOption": self.display_option,
            "height": self.height,
            "width": self.width,
        }

    def to_pbir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "page.json").write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        visuals_path = path / "visuals"
        if visuals_path.exists():
            shutil.rmtree(visuals_path)
        visuals_path.mkdir()
        for visual in self.visuals:
            visual.to_pbir(visuals_path / visual.name)

    @classmethod
    def from_pbir(cls, path: Path) -> "Page":
        data = json.loads((path / "page.json").read_text(encoding="utf-8"))
        page = cls(
            name=data["name"],
            display_name=data["displayName"],
            width=data.get("width", 1280),
            height=data.get("height", 720),
            display_option=data.get("displayOption", "FitToPage"),
            raw_page_data=data,
        )
        visuals_path = path / "visuals"
        if visuals_path.exists():
            for visual_dir in sorted(visuals_path.iterdir()):
                if visual_dir.is_dir() and (visual_dir / "visual.json").exists():
                    page.visuals.append(Visual.from_pbir(visual_dir))
        return page
