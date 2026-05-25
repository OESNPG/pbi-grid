import pytest

from src.grid.schema import LayoutSpec
from src.grid.engine import build
from src.grid.renderer import render
from .conftest import json_files


@pytest.mark.integration
class TestGenerateDefault:
    @pytest.fixture(scope="class")
    def generated(self, layout_default, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("default_gen")
        layout = LayoutSpec.from_yaml(layout_default)
        report = build(layout)
        return render(report, tmp, source_report_path=layout.source_report_path)

    @pytest.fixture(scope="class")
    def generated_files(self, generated):
        return json_files(generated)

    def test_same_json_files(self, generated_files, golden_default):
        # All files present in the golden must exist in generated.
        # Extra files in generated (e.g. new source-report visuals) are not regressions.
        missing = set(golden_default.keys()) - set(generated_files.keys())
        assert not missing, f"Files missing from generated: {missing}"

    def test_pages_json_matches(self, generated_files, golden_default):
        key = "definition/pages/pages.json"
        assert generated_files[key] == golden_default[key]

    def test_report_json_matches(self, generated_files, golden_default):
        key = "definition/report.json"
        assert generated_files[key] == golden_default[key]

    def test_each_visual_matches(self, generated_files, golden_default):
        visual_keys = [k for k in golden_default if "visuals" in k and k.endswith("visual.json")]
        for key in visual_keys:
            assert generated_files[key] == golden_default[key], f"Mismatch in {key}"

    def test_each_page_matches(self, generated_files, golden_default):
        page_keys = [k for k in golden_default if k.endswith("page.json")]
        for key in page_keys:
            assert generated_files[key] == golden_default[key], f"Mismatch in {key}"

    def test_registered_resources_matches(self, generated_files, golden_default):
        rr_keys = [k for k in golden_default if "RegisteredResources" in k]
        for key in rr_keys:
            assert generated_files[key] == golden_default[key], f"Mismatch in {key}"
