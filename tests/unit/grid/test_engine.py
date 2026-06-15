import pytest

from src.grid.engine import _find_next_x, _rowspan_height, _build_page, _apply_shared
from src.grid.schema import Canvas, ColSpec, RowSpec, PageSpec, SharedRowSpec, OverlaySpec, ColConfig, InfoSpec
from src.models import Visual, Position

# ── Helpers ───────────────────────────────────────────────────────────────────

_PAGE_ID = "a" * 20  # valid 20-char lowercase hex


def _pmap(page: PageSpec) -> dict[str, str]:
    return {page.display_name: _PAGE_ID}


def _page(rows: list[RowSpec], id: str = "p") -> PageSpec:
    return PageSpec(id=id, display_name=id, rows=rows)


def _row(id: str, height: int, cols: list[ColSpec]) -> RowSpec:
    return RowSpec(id=id, height=height, cols=cols)


def _col(span: int, **kwargs) -> ColSpec:
    return ColSpec(span=span, **kwargs)


# ── Group A: _find_next_x ─────────────────────────────────────────────────────

class TestFindNextX:
    def test_no_blocked(self):
        assert _find_next_x(0.0, 100.0, []) == 0.0

    def test_single_block_before(self):
        # block ends at 50, x_start=60 — no overlap
        assert _find_next_x(60.0, 40.0, [(0.0, 50.0)]) == 60.0

    def test_single_block_overlap(self):
        # block [0..100], asking x=50 w=60 — must jump to 100
        assert _find_next_x(50.0, 60.0, [(0.0, 100.0)]) == 100.0

    def test_adjacent_blocks(self):
        # [0..50] and [50..100] — must chain-jump to 100
        assert _find_next_x(0.0, 10.0, [(0.0, 50.0), (50.0, 50.0)]) == 100.0

    def test_block_after_x(self):
        # block starts at 200, width fits before it
        assert _find_next_x(0.0, 100.0, [(200.0, 50.0)]) == 0.0


# ── Group B: _rowspan_height ──────────────────────────────────────────────────

class TestRowspanHeight:
    def _rows(self):
        return [
            RowSpec(id="r0", height=100, cols=[]),
            RowSpec(id="r1", height=200, cols=[]),
        ]

    def test_rowspan_1(self):
        assert _rowspan_height(self._rows(), 0, 1) == 100

    def test_rowspan_2(self):
        assert _rowspan_height(self._rows(), 0, 2) == 300

    def test_rowspan_beyond_end(self):
        # rowspan=5 exceeds 2 rows — clamped to available
        assert _rowspan_height(self._rows(), 0, 5) == 300


# ── Group C: _build_page — basic positioning ──────────────────────────────────

class TestBuildPagePositioning:
    def test_single_col_full_width(self):
        canvas = Canvas(width=1280, height=720, gutter=4)
        page = _page([_row("r0", 100, [_col(12)])])
        result = _build_page(page, canvas, _pmap(page))
        v = result.visuals[0]
        assert pytest.approx(v.position.x, abs=0.01) == 2.0      # g = gutter/2 = 2
        assert pytest.approx(v.position.width, abs=0.01) == 1276.0  # 1280 - 2*2

    def test_two_cols_equal_span(self):
        canvas = Canvas(width=1280, height=720, gutter=4)
        # col_unit = 1280/12 = 106.666...; span=6 → raw_w=640; g=2
        page = _page([_row("r0", 100, [_col(6), _col(6)])])
        result = _build_page(page, canvas, _pmap(page))
        v0, v1 = result.visuals[0], result.visuals[1]
        assert pytest.approx(v0.position.x, abs=0.01) == 2.0
        assert pytest.approx(v0.position.width, abs=0.01) == 636.0   # 640 - 4
        assert pytest.approx(v1.position.x, abs=0.01) == 642.0       # 640 + 2
        assert pytest.approx(v1.position.width, abs=0.01) == 636.0

    def test_gutter_zero(self):
        canvas = Canvas(width=1280, height=720, gutter=0)
        page = _page([_row("r0", 100, [_col(12)])])
        result = _build_page(page, canvas, _pmap(page))
        v = result.visuals[0]
        assert pytest.approx(v.position.x, abs=0.01) == 0.0
        assert pytest.approx(v.position.width, abs=0.01) == 1280.0

    def test_y_offset_accumulates(self):
        canvas = Canvas(width=1280, height=720, gutter=0)
        page = _page([
            _row("r0", 100, [_col(12)]),
            _row("r1", 200, [_col(12)]),
            _row("r2", 50,  [_col(12)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        assert pytest.approx(result.visuals[0].position.y, abs=0.01) == 0.0
        assert pytest.approx(result.visuals[1].position.y, abs=0.01) == 100.0
        assert pytest.approx(result.visuals[2].position.y, abs=0.01) == 300.0

    def test_z_increments(self):
        canvas = Canvas(width=1280, height=100, gutter=0)
        page = _page([_row("r0", 100, [_col(6), _col(6)])])
        result = _build_page(page, canvas, _pmap(page))
        assert result.visuals[0].position.z == 1000
        assert result.visuals[1].position.z == 2000


# ── Group D: _build_page — rowspan carry ─────────────────────────────────────

class TestBuildPageRowspan:
    def test_rowspan_blocks_next_row(self):
        # col span=3, rowspan=2 in row0 → row1 col pushed right by 3 col_units (320px)
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(3, rowspan=2), _col(9)]),
            _row("r1", 100, [_col(9)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        # visuals: r0c0(rowspan), r0c1, r1c0
        r1_col = result.visuals[2]
        assert pytest.approx(r1_col.position.x, abs=0.01) == 320.0

    def test_rowspan_prepend(self):
        # rowspan col at start of row0 → row1 col starts after the block
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(3, rowspan=2)]),
            _row("r1", 100, [_col(9)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        r1_col = result.visuals[1]
        assert pytest.approx(r1_col.position.x, abs=0.01) == 320.0

    def test_rowspan_append(self):
        # rowspan col at end of row0 → row1 starts at 0 (block is after the col)
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(9), _col(3, rowspan=2)]),
            _row("r1", 100, [_col(9)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        r1_col = result.visuals[2]
        assert pytest.approx(r1_col.position.x, abs=0.01) == 0.0

    def test_rowspan_multiple(self):
        # two rowspan=2 cols in row0 (span 3 each) → row1 has 640px blocked
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(3, rowspan=2), _col(3, rowspan=2), _col(6)]),
            _row("r1", 100, [_col(6)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        r1_col = result.visuals[3]
        # two spans of 3 = 6 col_units = 640px blocked
        assert pytest.approx(r1_col.position.x, abs=0.01) == 640.0


# ── Group E: _build_page — overflow and clamp ─────────────────────────────────

class TestBuildPageOverflow:
    def test_span_overflow_clamped(self, capsys):
        # row0: span=12 rowspan=2 → blocks entire width in row1
        # row1: span=12 → x jumps to 1280, available=0, width clamped to 0
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(12, rowspan=2)]),
            _row("r1", 100, [_col(12)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        overflow_v = result.visuals[1]
        assert pytest.approx(overflow_v.position.width, abs=0.01) == 0.0

    def test_span_overflow_partial(self, capsys):
        # 3 cols blocked (320px) in row1; span=9 → raw_w=960, available=960, fits fine
        # span=12 with 3 blocked → available=960, raw_w=1280 → clamped to 960
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(3, rowspan=2), _col(9)]),
            _row("r1", 100, [_col(12)]),
        ])
        result = _build_page(page, canvas, _pmap(page))
        # row1 col: x=320, available=960, raw_w=1280 → clamped to 960
        r1_col = result.visuals[2]
        assert pytest.approx(r1_col.position.width, abs=0.01) == 960.0

    def test_overflow_prints_warning(self, capsys):
        canvas = Canvas(width=1280, height=200, gutter=0)
        page = _page([
            _row("r0", 100, [_col(12, rowspan=2)]),
            _row("r1", 100, [_col(12, visual="textbox")]),
        ])
        _build_page(page, canvas, _pmap(page))
        out = capsys.readouterr().out
        assert "WARNING" in out


# ── Group F: _build_page — height override and valign ────────────────────────

class TestBuildPageValign:
    def test_col_height_override(self):
        canvas = Canvas(width=1280, height=60, gutter=0)
        page = _page([_row("r0", 60, [_col(12, height=30.0)])])
        result = _build_page(page, canvas, _pmap(page))
        assert pytest.approx(result.visuals[0].position.height, abs=0.01) == 30.0

    def test_valign_center(self):
        # cell_h=60, col_h=30, dy=(60-30)/2=15
        canvas = Canvas(width=1280, height=60, gutter=0)
        page = _page([_row("r0", 60, [_col(12, height=30.0, valign="center")])])
        result = _build_page(page, canvas, _pmap(page))
        assert pytest.approx(result.visuals[0].position.y, abs=0.01) == 15.0

    def test_valign_bottom(self):
        # cell_h=60, col_h=30, dy=30
        canvas = Canvas(width=1280, height=60, gutter=0)
        page = _page([_row("r0", 60, [_col(12, height=30.0, valign="bottom")])])
        result = _build_page(page, canvas, _pmap(page))
        assert pytest.approx(result.visuals[0].position.y, abs=0.01) == 30.0

    def test_valign_top_default(self):
        canvas = Canvas(width=1280, height=60, gutter=0)
        page = _page([_row("r0", 60, [_col(12)])])
        result = _build_page(page, canvas, _pmap(page))
        assert pytest.approx(result.visuals[0].position.y, abs=0.01) == 0.0


# ── Group G: _build_page — border shapes ─────────────────────────────────────

_TOKENS = {"layout": {"border_color": "#E0E0E0", "border_weight": 1, "border_radius": 0}}


class TestBuildPageBorder:
    def test_col_border_adds_shape(self):
        canvas = Canvas(width=1280, height=60, gutter=0)
        page = _page([_row("r0", 60, [_col(12, border=True)])])
        result = _build_page(page, canvas, _pmap(page), tokens=_TOKENS)
        shapes = [v for v in result.visuals if v.visual_type == "shape"]
        assert len(shapes) >= 1

    def test_row_border_adds_shape(self):
        canvas = Canvas(width=1280, height=60, gutter=0)
        row = RowSpec(id="r0", height=60, cols=[_col(12)], border=True)
        page = _page([row])
        result = _build_page(page, canvas, _pmap(page), tokens=_TOKENS)
        shapes = [v for v in result.visuals if v.visual_type == "shape"]
        assert len(shapes) >= 1

    def test_no_border_by_default(self):
        canvas = Canvas(width=1280, height=60, gutter=0)
        page = _page([_row("r0", 60, [_col(12)])])
        result = _build_page(page, canvas, _pmap(page))
        shapes = [v for v in result.visuals if v.visual_type == "shape"]
        assert len(shapes) == 0


# ── Group H: _apply_shared ────────────────────────────────────────────────────

class TestApplyShared:
    def test_shared_row_prepends_cols(self):
        sr_col = _col(3)
        shared = SharedRowSpec(id="nav", cols=[sr_col], height=60)
        page = _page([_row("nav", 60, [_col(9)])])
        result = _apply_shared(page, [shared])
        assert result.rows[0].cols[0] is sr_col

    def test_shared_row_missing_id(self):
        shared = SharedRowSpec(id="nav", cols=[_col(3)], height=60)
        page = _page([_row("content", 200, [_col(12)])])
        result = _apply_shared(page, [shared])
        assert result.rows[0].id == "nav"
        assert result.rows[1].id == "content"

    def test_no_shared_rows(self):
        page = _page([_row("r0", 100, [_col(12)])])
        result = _apply_shared(page, [])
        assert result is page


# ── Canvas por página ─────────────────────────────────────────────────────────
class TestPerPageCanvas:
    def test_apply_shared_preserves_canvas(self):
        own = Canvas(width=1600, height=2000, gutter=0)
        page = PageSpec(id="p", display_name="p",
                        rows=[_row("r0", 100, [_col(12)])], canvas=own)
        shared = SharedRowSpec(id="nav", cols=[_col(12)], height=60)
        result = _apply_shared(page, [shared])
        assert result.canvas is own

    def test_build_uses_per_page_canvas(self):
        from src.grid.engine import build
        from src.grid.schema import LayoutSpec

        def mkpage(pid, name, canvas=None):
            return PageSpec(
                id=pid, display_name=name,
                rows=[_row("r0", 100, [_col(12, visual="textbox")])],
                canvas=canvas,
            )

        layout = LayoutSpec(
            report_name="R", package=None,
            canvas=Canvas(width=1280, height=720, gutter=0),
            pages=[
                mkpage("a" * 20, "Global"),
                mkpage("b" * 20, "Propria", Canvas(width=1600, height=2000, gutter=0)),
            ],
        )
        report = build(layout)
        pages = {p.display_name: p for p in report.pages}

        # página sem canvas próprio usa o global
        assert pages["Global"].width == 1280
        assert pytest.approx(pages["Global"].visuals[0].position.width, abs=0.01) == 1280

        # página com canvas próprio usa as suas dimensões
        assert pages["Propria"].width == 1600
        assert pages["Propria"].height == 2000
        assert pytest.approx(pages["Propria"].visuals[0].position.width, abs=0.01) == 1600


# ── Normalização de fonte de textbox ──────────────────────────────────────────
def _textbox_source(name: str, fonts: list) -> Visual:
    """Textbox de source com um textRun por fonte informada (None = sem override)."""
    runs = []
    for f in fonts:
        run = {"value": "x"}
        if f is not None:
            run["textStyle"] = {"fontFamily": f}
        runs.append(run)
    raw = {
        "name": name,
        "position": {"x": 0, "y": 0, "z": 0, "width": 10, "height": 10},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": runs}]}}]},
        },
    }
    return Visual(name=name, visual_type="textbox",
                  position=Position(x=0, y=0, z=0, width=10, height=10, tab_order=0),
                  raw_data=raw)


def _runs_fonts(visual: Visual) -> list:
    out = []
    for g in visual.raw_data["visual"]["objects"]["general"]:
        for p in g["properties"]["paragraphs"]:
            for r in p["textRuns"]:
                out.append(r.get("textStyle", {}).get("fontFamily"))
    return out


class TestTextboxFontNormalization:
    _CANVAS = Canvas(width=1280, height=720, gutter=0)
    _TOKENS = {"typography": {"text_font": "Trebuchet MS"}}

    def test_forca_fonte_em_todos_os_runs(self):
        # título com fonte explícita "errada" + subtítulo sem override
        src = _textbox_source("tb1", ["Segoe (Bold)", None])
        page = _page([_row("r0", 100, [_col(12, name="tb1")])])
        result = _build_page(page, self._CANVAS, _pmap(page),
                             source_visuals={"tb1": src}, tokens=self._TOKENS)
        assert _runs_fonts(result.visuals[0]) == ["Trebuchet MS", "Trebuchet MS"]

    def test_nao_muta_o_source(self):
        src = _textbox_source("tb1", ["Segoe (Bold)"])
        page = _page([_row("r0", 100, [_col(12, name="tb1")])])
        _build_page(page, self._CANVAS, _pmap(page),
                    source_visuals={"tb1": src}, tokens=self._TOKENS)
        # o raw_data do source permanece intacto (deep copy no engine)
        assert _runs_fonts(src) == ["Segoe (Bold)"]

    def test_sem_token_nao_altera(self):
        src = _textbox_source("tb1", ["Segoe (Bold)"])
        page = _page([_row("r0", 100, [_col(12, name="tb1")])])
        result = _build_page(page, self._CANVAS, _pmap(page),
                             source_visuals={"tb1": src}, tokens={})
        assert _runs_fonts(result.visuals[0]) == ["Segoe (Bold)"]


# ── Overlay (card sobre donut) ─────────────────────────────────────────────────
class TestOverlay:
    _CANVAS = Canvas(width=1280, height=720, gutter=0)

    def test_overlay_centralizado_e_acima(self):
        # célula cheia 1280x100; overlay 90x50 centralizado
        col = _col(12, visual="donutChart",
                   overlay=[OverlaySpec(visual="card", width=90, height=50)])
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page))
        donut, card = result.visuals[0], result.visuals[1]
        assert donut.visual_type == "donutChart"
        assert card.visual_type == "card"
        assert pytest.approx(card.position.x, abs=0.01) == (1280 - 90) / 2
        assert pytest.approx(card.position.y, abs=0.01) == (100 - 50) / 2
        assert pytest.approx(card.position.width, abs=0.01) == 90
        assert pytest.approx(card.position.height, abs=0.01) == 50
        # overlay precisa ficar ACIMA da célula-pai (z maior)
        assert card.position.z > donut.position.z

    def test_overlay_align_right_valign_bottom(self):
        col = _col(12, visual="donutChart",
                   overlay=[OverlaySpec(visual="card", width=100, height=40,
                                        align="right", valign="bottom")])
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page))
        card = result.visuals[1]
        assert pytest.approx(card.position.x, abs=0.01) == 1280 - 100
        assert pytest.approx(card.position.y, abs=0.01) == 100 - 40

    def test_overlay_referencia_visual_do_source(self):
        src = Visual(name="card1", visual_type="cardVisual",
                     position=Position(x=0, y=0, z=0, width=1, height=1, tab_order=0),
                     raw_data={"name": "card1", "visual": {"visualType": "cardVisual"}})
        col = _col(6, name="donutX",
                   overlay=[OverlaySpec(name="card1", width=80, height=40)])
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page),
                             source_visuals={"card1": src})
        card = result.visuals[-1]
        assert card.name == "card1"
        assert card.visual_type == "cardVisual"
        assert card.raw_data is not None

    def test_sem_overlay_nao_adiciona_visual(self):
        page = _page([_row("r0", 100, [_col(12, visual="donutChart")])])
        result = _build_page(page, self._CANVAS, _pmap(page))
        assert len(result.visuals) == 1


# -- Title injection (config.title) --------------------------------------------
def _title_lit(visual_raw):
    return visual_raw["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]


class TestTitleInjection:
    _CANVAS = Canvas(width=1280, height=720, gutter=0)

    def _src(self, name="c"):
        return Visual(name=name, visual_type="barChart",
                      position=Position(x=0, y=0, z=0, width=1, height=1, tab_order=0),
                      raw_data={"name": name, "visual": {"visualType": "barChart"}})

    def test_title_injeta_no_visual_do_source(self):
        col = _col(12, name="c", config=ColConfig(title="Atuacao nos temas"))
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page), source_visuals={"c": self._src()})
        assert _title_lit(result.visuals[0].raw_data) == "'Atuacao nos temas'"

    def test_title_escapa_aspas_simples(self):
        col = _col(12, name="c", config=ColConfig(title="Total de PPG's mapeados"))
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page), source_visuals={"c": self._src()})
        assert _title_lit(result.visuals[0].raw_data) == "'Total de PPG''s mapeados'"

    def test_title_preserva_alignment_existente(self):
        src = self._src()
        src.raw_data["visual"]["visualContainerObjects"] = {
            "title": [{"properties": {"alignment": {"expr": {"Literal": {"Value": "'center'"}}}}}]
        }
        col = _col(12, name="c", config=ColConfig(title="Novo titulo"))
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page), source_visuals={"c": src})
        props = result.visuals[0].raw_data["visual"]["visualContainerObjects"]["title"][0]["properties"]
        assert props["text"]["expr"]["Literal"]["Value"] == "'Novo titulo'"
        assert props["alignment"]["expr"]["Literal"]["Value"] == "'center'"

    def test_sem_config_nao_injeta(self):
        page = _page([_row("r0", 100, [_col(12, name="c")])])
        result = _build_page(page, self._CANVAS, _pmap(page), source_visuals={"c": self._src()})
        assert "visualContainerObjects" not in result.visuals[0].raw_data["visual"]
        assert all(v.visual_type != "textbox" for v in result.visuals)

    def test_config_sem_title_nao_injeta(self):
        col = _col(12, name="c", config=ColConfig(info=InfoSpec(description="<b>html</b>")))
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page), source_visuals={"c": self._src()})
        assert "visualContainerObjects" not in result.visuals[0].raw_data["visual"]

    def test_title_card_sobrescreve_displayname(self):
        # cardVisual: o rótulo é o displayName da projeção, não o título de header
        src = Visual(name="c", visual_type="cardVisual",
                     position=Position(x=0, y=0, z=0, width=1, height=1, tab_order=0),
                     raw_data={"name": "c", "visual": {"visualType": "cardVisual", "query": {
                         "queryState": {"Data": {"projections": [{"field": {}, "displayName": "Velho"}]}}}}})
        col = _col(12, name="c", config=ColConfig(title="Novo Rotulo"))
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page), source_visuals={"c": src})
        proj = result.visuals[0].raw_data["visual"]["query"]["queryState"]["Data"]["projections"][0]
        assert proj["displayName"] == "Novo Rotulo"
        assert "visualContainerObjects" not in result.visuals[0].raw_data["visual"]

    def test_title_em_visual_bare(self):
        col = _col(12, visual="barChart", config=ColConfig(title="Bare"))
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page))
        vco = result.visuals[0].config["visualContainerObjects"]
        assert vco["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"] == "'Bare'"


    def test_overlay_offset_empurra_para_baixo(self):
        # centralizado + offset_y desce o card (título/legenda no topo do donut)
        col = _col(12, visual="donutChart",
                   overlay=[OverlaySpec(visual="card", width=90, height=50, offset_y=18)])
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page))
        card = result.visuals[1]
        assert pytest.approx(card.position.y, abs=0.01) == (100 - 50) / 2 + 18
        # x permanece centralizado (offset_x default 0)
        assert pytest.approx(card.position.x, abs=0.01) == (1280 - 90) / 2

    def test_overlay_offset_negativo(self):
        col = _col(12, visual="donutChart",
                   overlay=[OverlaySpec(visual="card", width=90, height=50,
                                        offset_x=-10, offset_y=-5)])
        page = _page([_row("r0", 100, [col])])
        result = _build_page(page, self._CANVAS, _pmap(page))
        card = result.visuals[1]
        assert pytest.approx(card.position.x, abs=0.01) == (1280 - 90) / 2 - 10
        assert pytest.approx(card.position.y, abs=0.01) == (100 - 50) / 2 - 5
