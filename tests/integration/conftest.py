import json
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
EXAMPLES = ROOT / "examples" / "countries_population"
GOLDEN = ROOT / "tests" / "golden" / "countries_population"

_SKIP_NAMES = {"localSettings.json", "editorSettings.json"}
# SharedResources/ contains BaseTheme JSON blobs that are not versioned in golden
# (update-golden.ps1 only copies RegisteredResources/).
_SKIP_DIRS = {"SharedResources"}


def json_files(base_dir: Path) -> dict[str, dict]:
    """Return {relative_posix_path: parsed_json} for all non-excluded JSON files."""
    result = {}
    for f in base_dir.rglob("*.json"):
        if f.name in _SKIP_NAMES:
            continue
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        result[f.relative_to(base_dir).as_posix()] = json.loads(f.read_text(encoding="utf-8"))
    return result


@pytest.fixture(scope="session")
def source_report():
    return EXAMPLES / "source" / "countries_population.Report"


@pytest.fixture(scope="session")
def layout_default():
    return EXAMPLES / "pbi_grid_default_theme_layout.yaml"


@pytest.fixture(scope="session")
def layout_govbr():
    return EXAMPLES / "pbi_grid_govbr_theme_layout.yaml"


@pytest.fixture(scope="session")
def golden_default():
    return json_files(GOLDEN / "default")


@pytest.fixture(scope="session")
def golden_govbr():
    return json_files(GOLDEN / "govbr")
