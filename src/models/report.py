import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .page import Page

_REPORT_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.2.0/schema.json"
_PAGES_SCHEMA  = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
_PBIR_SCHEMA   = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
_VERSION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"


@dataclass
class Report:
    name: str
    theme: str = "CY26SU02"
    pages: list[Page] = field(default_factory=list)
    dataset_reference: dict | None = None   # content of definition.pbir datasetReference
    raw_report_data: dict | None = None     # full report.json when loaded from existing report
    active_page_name: str | None = None     # activePageName from pages.json source
    registered_resources: list[tuple[str, Path]] = field(default_factory=list)  # (item_name, source_path)

    def add_page(self, page: Page) -> None:
        self.pages.append(page)

    def get_page(self, display_name: str) -> Page | None:
        return next((p for p in self.pages if p.display_name == display_name), None)

    def _with_registered_resources(self, report_dict: dict) -> dict:
        if not self.registered_resources:
            return report_dict
        items = [
            {"name": name, "path": name, "type": "Image"}
            for name, _ in self.registered_resources
        ]
        new_pkg = {
            "name": "RegisteredResources",
            "type": "RegisteredResources",
            "items": items,
        }
        result = dict(report_dict)
        existing = [
            p for p in result.get("resourcePackages", [])
            if p.get("name") != "RegisteredResources"
        ]
        existing.append(new_pkg)
        result["resourcePackages"] = existing
        return result

    def _report_dict(self) -> dict:
        return {
            "$schema": _REPORT_SCHEMA,
            "themeCollection": {
                "baseTheme": {
                    "name": self.theme,
                    "type": "SharedResources",
                }
            },
        }

    def _pages_dict(self) -> dict:
        page_names = [p.name for p in self.pages]
        active = (
            self.active_page_name
            if self.active_page_name and self.active_page_name in page_names
            else (page_names[0] if page_names else "")
        )
        return {
            "$schema": _PAGES_SCHEMA,
            "pageOrder": page_names,
            "activePageName": active,
        }

    def _pbir_dict(self) -> dict:
        ref = self.dataset_reference or {
            "byPath": {"path": f"../{self.name}.SemanticModel"}
        }
        return {
            "$schema": _PBIR_SCHEMA,
            "version": "4.0",
            "datasetReference": ref,
        }

    def to_pbir(self, path: Path) -> None:
        definition = path / "definition"
        definition.mkdir(parents=True, exist_ok=True)

        (path / "definition.pbir").write_text(
            json.dumps(self._pbir_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        (definition / "version.json").write_text(
            json.dumps(
                {"$schema": _VERSION_SCHEMA, "version": "2.0.0"},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        report_content = self.raw_report_data if self.raw_report_data is not None else self._report_dict()
        report_content = self._with_registered_resources(report_content)
        (definition / "report.json").write_text(
            json.dumps(report_content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if self.registered_resources:
            res_dir = path / "StaticResources" / "RegisteredResources"
            res_dir.mkdir(parents=True, exist_ok=True)
            for item_name, src_path in self.registered_resources:
                shutil.copy2(src_path, res_dir / item_name)

        pages_dir = definition / "pages"
        pages_dir.mkdir(exist_ok=True)

        (pages_dir / "pages.json").write_text(
            json.dumps(self._pages_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        for page in self.pages:
            page.to_pbir(pages_dir / page.name)

    @classmethod
    def from_pbir(cls, path: Path) -> "Report":
        definition = path / "definition"
        report_data = json.loads((definition / "report.json").read_text(encoding="utf-8"))
        theme = (
            report_data.get("themeCollection", {})
            .get("baseTheme", {})
            .get("name", "CY26SU02")
        )
        pages_data = json.loads(
            (definition / "pages" / "pages.json").read_text(encoding="utf-8")
        )

        dataset_reference: dict | None = None
        pbir_path = path / "definition.pbir"
        if pbir_path.exists():
            pbir_data = json.loads(pbir_path.read_text(encoding="utf-8"))
            dataset_reference = pbir_data.get("datasetReference")

        report = cls(
            name=path.stem,
            theme=theme,
            dataset_reference=dataset_reference,
            raw_report_data=report_data,
            active_page_name=pages_data.get("activePageName"),
        )
        for page_id in pages_data.get("pageOrder", []):
            page_path = definition / "pages" / page_id
            if page_path.exists():
                report.pages.append(Page.from_pbir(page_path))
        return report
