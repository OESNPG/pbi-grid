import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .page import Page

_REPORT_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.2.0/schema.json"
_PAGES_SCHEMA  = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
_PBIR_SCHEMA   = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
_VERSION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"

# Versions required by Power BI in themeCollection.baseTheme.reportVersionAtImport
_THEME_VERSION_AT_IMPORT = {"visual": "2.8.0", "report": "3.2.0", "page": "2.3.1"}
# Version used for customTheme (RegisteredResources) — matches schema 3.3.0 observed from Desktop
_CUSTOM_THEME_VERSION_AT_IMPORT = {"visual": "2.9.0", "report": "3.3.0", "page": "2.3.1"}


@dataclass
class Report:
    name: str
    theme: str = "CY26SU02"
    pages: list[Page] = field(default_factory=list)
    dataset_reference: dict | None = None   # content of definition.pbir datasetReference
    raw_report_data: dict | None = None     # full report.json when loaded from existing report
    active_page_name: str | None = None     # activePageName from pages.json source
    registered_resources: list[tuple[str, Path]] = field(default_factory=list)  # (item_name, source_path)
    palette_name: str | None = None         # theme file name, e.g. "govbr"
    palette_data: dict | None = None        # full theme JSON dict written to BaseThemes/
    config_table_tmdl: str | None = None     # generated `config` table TMDL (info-modal data); written to the SemanticModel at render

    def add_page(self, page: Page) -> None:
        self.pages.append(page)

    def get_page(self, display_name: str) -> Page | None:
        return next((p for p in self.pages if p.display_name == display_name), None)

    @property
    def _custom_theme_filename(self) -> str | None:
        return f"{self.palette_name}custom.json" if self.palette_name else None

    def _with_palette_theme(self, report_dict: dict) -> dict:
        if not self.palette_name:
            return report_dict
        result = dict(report_dict)
        result["themeCollection"] = {
            "baseTheme": {
                "name": self.palette_name,
                "reportVersionAtImport": _THEME_VERSION_AT_IMPORT,
                "type": "SharedResources",
            },
            "customTheme": {
                "name": self._custom_theme_filename,
                "reportVersionAtImport": _CUSTOM_THEME_VERSION_AT_IMPORT,
                "type": "RegisteredResources",
            },
        }
        shared_pkg = {
            "name": "SharedResources",
            "type": "SharedResources",
            "items": [{
                "name": self.palette_name,
                "path": f"BaseThemes/{self.palette_name}.json",
                "type": "BaseTheme",
            }],
        }
        existing = [
            p for p in result.get("resourcePackages", [])
            if p.get("name") != "SharedResources"
        ]
        existing.insert(0, shared_pkg)
        result["resourcePackages"] = existing
        return result

    def _with_registered_resources(self, report_dict: dict) -> dict:
        custom_theme = self._custom_theme_filename
        image_items = [
            {"name": name, "path": name, "type": "Image"}
            for name, _ in self.registered_resources
        ]
        theme_items = (
            [{"name": custom_theme, "path": custom_theme, "type": "CustomTheme"}]
            if custom_theme else []
        )
        items = theme_items + image_items
        if not items:
            return report_dict
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
            json.dumps(self._pbir_dict(), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        (definition / "version.json").write_text(
            json.dumps({"$schema": _VERSION_SCHEMA, "version": "2.0.0"}, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        report_content = self.raw_report_data if self.raw_report_data is not None else self._report_dict()
        report_content = self._with_palette_theme(report_content)
        report_content = self._with_registered_resources(report_content)
        (definition / "report.json").write_text(
            json.dumps(report_content, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        if self.palette_data and self.palette_name:
            theme_dir = path / "StaticResources" / "SharedResources" / "BaseThemes"
            theme_dir.mkdir(parents=True, exist_ok=True)
            (theme_dir / f"{self.palette_name}.json").write_text(
                json.dumps(self.palette_data, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )

        res_dir = path / "StaticResources" / "RegisteredResources"
        if self.palette_data and self._custom_theme_filename:
            res_dir.mkdir(parents=True, exist_ok=True)
            (res_dir / self._custom_theme_filename).write_text(
                json.dumps(self.palette_data, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )

        if self.registered_resources:
            res_dir.mkdir(parents=True, exist_ok=True)
            for item_name, src_path in self.registered_resources:
                shutil.copy2(src_path, res_dir / item_name)

        pages_dir = definition / "pages"
        pages_dir.mkdir(exist_ok=True)

        (pages_dir / "pages.json").write_text(
            json.dumps(self._pages_dict(), indent=2, ensure_ascii=False, sort_keys=True),
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
