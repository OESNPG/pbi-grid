import pytest

from src.grid.schema import (
    Canvas, ColSpec, LayoutSpec,
    _resolve_ref, _make_colspec, _parse_rows,
)


class TestResolveRef:
    def test_resolve_ref_known(self):
        shared = {"nav": {"span": 3, "component": "menu"}}
        result = _resolve_ref({"ref": "nav", "span": 6}, shared)
        assert result["component"] == "menu"
        assert result["span"] == 6  # local override wins

    def test_resolve_ref_unknown(self):
        with pytest.raises(ValueError, match="nav"):
            _resolve_ref({"ref": "nav"}, {})

    def test_resolve_ref_no_ref(self):
        col = {"span": 6, "name": "vis1"}
        assert _resolve_ref(col, {}) is col


class TestMakeColspec:
    def test_make_colspec_defaults(self):
        col = _make_colspec({"span": 12}, {})
        assert col.span == 12
        assert col.rowspan == 1
        assert col.valign == "top"
        assert col.border is False
        assert col.height is None

    def test_make_colspec_props(self):
        col = _make_colspec({"span": 6, "custom_key": "val", "items": []}, {})
        assert "custom_key" in col.props
        assert col.props["custom_key"] == "val"

    def test_make_colspec_height_float(self):
        col = _make_colspec({"span": 6, "height": 30}, {})
        assert col.height == 30.0
        assert isinstance(col.height, float)

    def test_make_colspec_border_weight_float(self):
        col = _make_colspec({"span": 6, "border": True, "border_weight": 2}, {})
        assert col.border is True
        assert col.border_weight == 2.0

    def test_make_colspec_no_overlay_by_default(self):
        col = _make_colspec({"span": 6}, {})
        assert col.overlay == []

    def test_make_colspec_config_reads_file(self, tmp_path):
        (tmp_path / "c.yaml").write_text(
            "title: Titulados\n"
            "footer: Fonte CAPES\n"
            "info:\n"
            "  title: Sobre\n"
            "  description: <b>html</b>\n"
            "  footer: rodapé\n",
            encoding="utf-8",
        )
        col = _make_colspec({"span": 6, "name": "v1", "config": "c.yaml"}, {}, base_dir=tmp_path)
        assert col.config.title == "Titulados"
        assert col.config.footer == "Fonte CAPES"
        assert col.config.info.title == "Sobre"
        assert col.config.info.description == "<b>html</b>"
        assert col.config.info.footer == "rodapé"
        assert "config" not in col.props

    def test_make_colspec_config_tries_yaml_extension(self, tmp_path):
        # path sem extensão → tenta .yaml
        (tmp_path / "c.yaml").write_text("title: Atuação\n", encoding="utf-8")
        col = _make_colspec({"span": 6, "config": "c"}, {}, base_dir=tmp_path)
        assert col.config.title == "Atuação"

    def test_make_colspec_config_blank_fields_are_none(self, tmp_path):
        (tmp_path / "c.yaml").write_text("title: T\nfooter: ''\ninfo:\n  title: '  '\n", encoding="utf-8")
        col = _make_colspec({"span": 6, "config": "c.yaml"}, {}, base_dir=tmp_path)
        assert col.config.title == "T"
        assert col.config.footer is None
        assert col.config.info.title is None

    def test_make_colspec_config_missing_is_none(self, tmp_path, capsys):
        col = _make_colspec({"span": 6, "config": "nao_existe"}, {}, base_dir=tmp_path)
        assert col.config is None
        assert "config file not found" in capsys.readouterr().out

    def test_make_colspec_no_config_by_default(self):
        assert _make_colspec({"span": 6}, {}).config is None

    def test_make_colspec_overlay_parsed(self):
        col = _make_colspec({
            "span": 6, "name": "donut",
            "overlay": [{"name": "card", "width": 90, "height": 50}],
        }, {})
        assert len(col.overlay) == 1
        ov = col.overlay[0]
        assert ov.name == "card"
        assert ov.width == 90.0 and ov.height == 50.0
        assert ov.align == "center" and ov.valign == "center"  # defaults
        # overlay não deve vazar para props
        assert "overlay" not in col.props


class TestParseRows:
    def test_parse_rows_empty_cols(self):
        rows = _parse_rows([{"id": "r0", "height": 100}], {})
        assert len(rows) == 1
        assert rows[0].id == "r0"
        assert rows[0].height == 100
        assert rows[0].cols == []

    def test_parse_rows_multiple(self):
        raw = [
            {"id": "r0", "height": 60, "cols": [{"span": 6}, {"span": 6}]},
            {"id": "r1", "height": 100, "cols": [{"span": 12}]},
        ]
        rows = _parse_rows(raw, {})
        assert len(rows) == 2
        assert len(rows[0].cols) == 2
        assert len(rows[1].cols) == 1


class TestLayoutSpecFromYaml:
    def test_layout_spec_basic(self, tmp_path):
        yaml_content = """\
report:
  name: TestReport
canvas:
  width: 1280
  height: 720
  gutter: 4
pages:
  - id: page1
    display_name: Page 1
    rows:
      - id: r0
        height: 100
        cols:
          - span: 12
"""
        f = tmp_path / "layout.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        spec = LayoutSpec.from_yaml(f)
        assert spec.report_name == "TestReport"
        assert spec.canvas.width == 1280
        assert spec.canvas.gutter == 4.0
        assert len(spec.pages) == 1
        assert spec.pages[0].display_name == "Page 1"
        assert len(spec.pages[0].rows) == 1

    def test_canvas_gutter_default(self, tmp_path):
        yaml_content = """\
report:
  name: R
canvas:
  width: 1280
  height: 720
pages: []
"""
        f = tmp_path / "layout.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        spec = LayoutSpec.from_yaml(f)
        assert spec.canvas.gutter == 0.0

    def test_per_page_canvas_override_and_inheritance(self, tmp_path):
        yaml_content = """\
report:
  name: R
canvas:
  width: 1280
  height: 720
  gutter: 4
pages:
  - id: page1
    display_name: UsaGlobal
    rows: []
  - id: page2
    display_name: Propria
    canvas:
      width: 1600
      height: 2000
    rows: []
"""
        f = tmp_path / "layout.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        spec = LayoutSpec.from_yaml(f)
        # página sem canvas próprio -> None (cai no canvas global)
        assert spec.pages[0].canvas is None
        # página com canvas próprio -> width/height próprios; gutter herdado do global
        pc = spec.pages[1].canvas
        assert pc is not None
        assert pc.width == 1600
        assert pc.height == 2000
        assert pc.gutter == 4.0

    def test_resolve_ref_at_parse_time(self, tmp_path):
        yaml_content = """\
report:
  name: R
shared:
  components:
    nav:
      span: 3
      component: menu
canvas:
  width: 1280
  height: 720
pages:
  - id: p
    rows:
      - id: r0
        height: 60
        cols:
          - ref: nav
            span: 4
"""
        f = tmp_path / "layout.yaml"
        f.write_text(yaml_content, encoding="utf-8")
        spec = LayoutSpec.from_yaml(f)
        col = spec.pages[0].rows[0].cols[0]
        assert col.component == "menu"
        assert col.span == 4  # local override
