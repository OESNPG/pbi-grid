import pytest

from src.grid.schema import LayoutSpec
from src.grid.engine import build
from src.grid.renderer import render
from .conftest import json_files


@pytest.mark.integration
class TestGenerateGovbr:
    @pytest.fixture(scope="class")
    def generated(self, layout_govbr, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("govbr_gen")
        layout = LayoutSpec.from_yaml(layout_govbr)
        report = build(layout)
        return render(report, tmp, source_report_path=layout.source_report_path)

    @pytest.fixture(scope="class")
    def generated_files(self, generated):
        return json_files(generated)

    def test_same_json_files(self, generated_files, golden_govbr):
        # All files present in the golden must exist in generated.
        # Extra files in generated (e.g. new source-report visuals) are not regressions.
        missing = set(golden_govbr.keys()) - set(generated_files.keys())
        assert not missing, f"Files missing from generated: {missing}"

    def test_pages_json_matches(self, generated_files, golden_govbr):
        key = "definition/pages/pages.json"
        assert generated_files[key] == golden_govbr[key]

    def test_report_json_matches(self, generated_files, golden_govbr):
        key = "definition/report.json"
        assert generated_files[key] == golden_govbr[key]

    def test_each_visual_matches(self, generated_files, golden_govbr):
        visual_keys = [k for k in golden_govbr if "visuals" in k and k.endswith("visual.json")]
        for key in visual_keys:
            assert generated_files[key] == golden_govbr[key], f"Mismatch in {key}"

    def test_each_page_matches(self, generated_files, golden_govbr):
        page_keys = [k for k in golden_govbr if k.endswith("page.json")]
        for key in page_keys:
            assert generated_files[key] == golden_govbr[key], f"Mismatch in {key}"

    def test_registered_resources_matches(self, generated_files, golden_govbr):
        rr_keys = [k for k in golden_govbr if "RegisteredResources" in k]
        for key in rr_keys:
            assert generated_files[key] == golden_govbr[key], f"Mismatch in {key}"
