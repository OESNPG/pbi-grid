"""info_icon.on_top: o ⓘ ganha keepLayerOrder e não some atrás de um mapa ao dar zoom."""
from src.grid.engine import _make_info_icon_card
from src.grid.schema import Cell, IconSpec, _make_iconspec


def _general(v):
    return v.config["visualContainerObjects"].get("general")


def test_on_top_liga_keep_layer_order():
    icon = _make_iconspec({"align": "left", "offset_x": 10, "on_top": True})
    assert icon.on_top is True
    v = _make_info_icon_card(Cell(0, 0, 500, 400, 1000), "mapa", 1700, {}, "azureMap", icon=icon)
    assert _general(v) == [{"properties": {"keepLayerOrder": {"expr": {"Literal": {"Value": "true"}}}}}]


def test_sem_on_top_nao_muda_nada():
    v = _make_info_icon_card(Cell(0, 0, 500, 400, 1000), "mapa", 1700, {}, "azureMap",
                             icon=IconSpec(align="left", offset_x=10))
    assert _general(v) is None
    v = _make_info_icon_card(Cell(0, 0, 500, 400, 1000), "mapa", 1700, {}, "azureMap")
    assert _general(v) is None
