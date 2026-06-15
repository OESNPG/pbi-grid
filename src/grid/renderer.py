import json
import shutil
from pathlib import Path

from ..models import Report

_PBIP_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"


def _write_pbip(report: Report, project_dir: Path) -> None:
    pbip = {
        "$schema": _PBIP_SCHEMA,
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{report.name}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }
    (project_dir / f"{report.name}.pbip").write_text(
        json.dumps(pbip, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _copy_project(source_dir: Path, dest_dir: Path) -> None:
    """Copy all items from source_dir into dest_dir, overwriting existing files."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for item in source_dir.iterdir():
        dest = dest_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def render(report: Report, output: Path, source_report_path: Path | None = None) -> Path:
    """Serialize report to PBIR folder structure.

    When *source_report_path* is provided and points to a different location than
    *output*, the entire source project directory is copied to *output* first, then
    the layout changes are applied on top (positions overwritten, all other data preserved).

    Returns the path to the generated .Report directory.
    """
    report_dir = (
        output
        if output.suffix == "" and output.name.endswith(".Report")
        else output / f"{report.name}.Report"
    )
    project_dir = report_dir.parent

    if source_report_path and source_report_path.exists():
        source_project_dir = source_report_path.parent
        if source_project_dir.resolve() != project_dir.resolve():
            _copy_project(source_project_dir, project_dir)

    report.to_pbir(report_dir)

    if report.config_table_tmdl:
        _write_config_table(report, project_dir)

    if not (project_dir / f"{report.name}.pbip").exists():
        _write_pbip(report, project_dir)

    return report_dir


def _write_config_table(report: Report, project_dir: Path) -> None:
    """Write the generated info-modal table into the project's SemanticModel.

    The info-modal HTML lives in a static table the HTML Content visuals read, plus
    a model.tmdl reference so the table is recognized even when the source project
    no longer declares it. The SemanticModel was copied alongside the .Report (or is
    the in-place source); we only touch the generated table file and the reference.
    """
    from .info_table import TABLE_NAME, register_config_in_model

    sm_def = project_dir / f"{report.name}.SemanticModel" / "definition"
    tables_dir = sm_def / "tables"
    if not tables_dir.exists():
        print(f"  WARNING: SemanticModel tables dir not found ({tables_dir}); skipped config table.")
        return
    (tables_dir / f"{TABLE_NAME}.tmdl").write_text(report.config_table_tmdl, encoding="utf-8")

    model = sm_def / "model.tmdl"
    if model.exists():
        text = model.read_text(encoding="utf-8")
        new = register_config_in_model(text)
        if new != text:
            model.write_text(new, encoding="utf-8")
    else:
        print(f"  WARNING: model.tmdl not found ({model}); '{TABLE_NAME}' not registered.")
