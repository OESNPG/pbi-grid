"""Visuais e páginas preservados do Desktop mantêm grupo e ajuste de exibição."""
from src.models.page import Page
from src.models.visual import Position, Visual


def _visual(keep_group):
    raw = {"name": "v1", "position": {}, "parentGroupName": "g1", "visual": {"visualType": "shapeMap"}}
    v = Visual(name="v1", visual_type="shapeMap", position=Position(x=0, y=0, z=0, width=10, height=10, tab_order=0), raw_data=raw)
    v.keep_group = keep_group
    return v.to_dict()


def test_visual_reposicionado_sai_do_grupo():
    assert "parentGroupName" not in _visual(False)


def test_visual_preservado_continua_no_grupo():
    assert _visual(True)["parentGroupName"] == "g1"


def test_pagina_mantem_o_ajuste_de_exibicao_do_desktop():
    p = Page(name="p", display_name="P", raw_page_data={"name": "p", "displayOption": "FitToWidth"})
    assert p.to_dict()["displayOption"] == "FitToWidth"
    assert Page(name="q", display_name="Q").to_dict()["displayOption"] == "FitToPage"


def test_espacador_empty_row_nao_vira_visual():
    from src.grid.engine import _render_col
    from src.grid.schema import ColSpec, RowSpec, PageSpec
    from src.models.visual import Position  # noqa: F401
    from src.grid.engine import Cell
    col = ColSpec(span=2, name="empty_row")
    row = RowSpec(id="r", height=10, cols=[col])
    page = PageSpec(id="p", display_name="P", rows=[row])
    out = _render_col(col, Cell(x=0, y=0, width=10, height=10, z=1000), 0, 0, 10, 10, row, page, {"P": "p"}, {}, {}, None, 1000)
    assert out == []
