import pytest

from src.grid.extractor import _cluster_y, _infer_span, validate_layout

_COL_UNIT = 1280 / 12  # 106.666...


class TestClusterY:
    def test_merges_nearby(self):
        # 0, 2, 4 are within CLUSTER_TOL=5 of each other — merge to one band
        result = _cluster_y([0.0, 2.0, 4.0, 100.0, 102.0])
        assert result == [0.0, 100.0]

    def test_separates_distant(self):
        result = _cluster_y([0.0, 100.0, 200.0])
        assert result == [0.0, 100.0, 200.0]

    def test_single_value(self):
        assert _cluster_y([50.0]) == [50.0]

    def test_deduplicates(self):
        # duplicate exact values are treated as one
        result = _cluster_y([10.0, 10.0, 20.0])
        assert result == [10.0, 20.0]


class TestInferSpan:
    def test_rounds_to_nearest(self):
        # width=320 → 320/106.666=3.0
        assert _infer_span(320.0, _COL_UNIT) == 3

    def test_clamp_min(self):
        assert _infer_span(1.0, _COL_UNIT) == 1

    def test_clamp_max(self):
        assert _infer_span(2000.0, _COL_UNIT) == 12

    def test_rounds_half_width(self):
        # half of canvas = 640 → 640/106.666 = 6.0
        assert _infer_span(640.0, _COL_UNIT) == 6


class TestValidateLayout:
    def _data(self, page_heights: list[int], canvas_height: int = 720):
        return {
            "canvas": {"height": canvas_height},
            "pages": [
                {
                    "id": f"p{i}",
                    "display_name": f"P{i}",
                    "rows": [{"height": h, "cols": []} for h in ([ph] if isinstance(ph, int) else ph)],
                }
                for i, ph in enumerate(page_heights)
            ],
        }

    def test_height_ok_no_adjustment(self, capsys):
        data = self._data([720], canvas_height=720)
        validate_layout(data)
        assert data["canvas"]["height"] == 720

    def test_height_adjusted_when_page_taller(self, capsys):
        data = self._data([800], canvas_height=720)
        validate_layout(data)
        assert data["canvas"]["height"] == 800

    def test_spans_overflow_warning(self, capsys):
        data = {
            "canvas": {"height": 720},
            "pages": [{
                "id": "p", "display_name": "P",
                "rows": [{"id": "r0", "height": 100, "cols": [{"span": 7}, {"span": 7}]}],
            }],
        }
        validate_layout(data)
        out = capsys.readouterr().out
        assert "overflow" in out.lower() or ">" in out

    def test_no_pages(self, capsys):
        data = {"canvas": {"height": 720}, "pages": []}
        validate_layout(data)  # should not crash
