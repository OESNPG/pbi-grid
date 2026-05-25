import pytest

from src.grid.engine import _find_next_x, _rowspan_height, _build_page, _apply_shared
from src.grid.schema import Canvas, ColSpec, RowSpec, PageSpec, SharedRowSpec

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
