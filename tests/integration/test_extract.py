import pytest
import yaml

from src.grid.extractor import extract


@pytest.mark.integration
class TestExtract:
    def test_returns_yaml_path(self, source_report, tmp_path):
        out = extract(source_report, output=tmp_path / "layout.yaml")
        assert out.exists()
        assert out.suffix == ".yaml"

    def test_pages_count_matches_report(self, source_report, tmp_path):
        out = extract(source_report, output=tmp_path / "layout.yaml")
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        pages_dir = source_report / "definition" / "pages"
        real_count = len([p for p in pages_dir.iterdir() if p.is_dir()])
        assert len(data["pages"]) == real_count

    def test_page_ids_match_folder_names(self, source_report, tmp_path):
        out = extract(source_report, output=tmp_path / "layout.yaml")
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        pages_dir = source_report / "definition" / "pages"
        folder_names = {p.name for p in pages_dir.iterdir() if p.is_dir()}
        extracted_ids = {p["id"] for p in data["pages"]}
        assert extracted_ids == folder_names

    def test_visuals_referenced_in_cols(self, source_report, tmp_path):
        out = extract(source_report, output=tmp_path / "layout.yaml")
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        all_col_names = {
            col["name"]
            for page_data in data["pages"]
            for row in page_data.get("rows", [])
            for col in row.get("cols", [])
            if col.get("name")
        }
        # The extract output must reference at least some visuals across all pages
        assert len(all_col_names) > 0, "Extract produced no visual name references"

    def test_merge_preserves_existing_pages(self, source_report, tmp_path):
        first = extract(source_report, output=tmp_path / "layout.yaml")
        data = yaml.safe_load(first.read_text(encoding="utf-8"))
        first_id = data["pages"][0]["id"]
        first_rows = data["pages"][0]["rows"]

        merged = extract(source_report, output=tmp_path / "merged.yaml", merge_with=first)
        merged_data = yaml.safe_load(merged.read_text(encoding="utf-8"))
        pages_by_id = {p["id"]: p for p in merged_data["pages"]}
        assert pages_by_id[first_id]["rows"] == first_rows

    def test_merge_preserves_comments(self, source_report, tmp_path):
        # gera um layout e injeta comentários (topo e antes de pages)
        base = extract(source_report, output=tmp_path / "layout.yaml")
        text = base.read_text(encoding="utf-8")
        commented = "# COMENTARIO DE TOPO\n" + text.replace(
            "pages:", "# COMENTARIO ANTES DE PAGES\npages:", 1
        )
        layout_file = tmp_path / "commented.yaml"
        layout_file.write_text(commented, encoding="utf-8")

        # merge sobre o mesmo report (nada novo) deve preservar os comentários
        merged = extract(source_report, output=tmp_path / "merged.yaml", merge_with=layout_file)
        out = merged.read_text(encoding="utf-8")
        assert "# COMENTARIO DE TOPO" in out
        assert "# COMENTARIO ANTES DE PAGES" in out
        assert yaml.safe_load(out)["pages"]  # continua válido
