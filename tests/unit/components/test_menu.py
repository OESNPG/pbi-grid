import pytest

from src.components.menu import MenuItem, MenuComponent, _flatten
from src.grid.schema import Cell

_VALID_ID = "a" * 20


def _cell(w=200, h=400):
    return Cell(x=0, y=0, width=w, height=h, z=1000)


class TestFlatten:
    def test_leaf_items(self):
        items = [MenuItem(page="p1"), MenuItem(page="p2")]
        flat = _flatten(items)
        assert len(flat) == 2
        assert all(not is_child for _, is_child in flat)

    def test_group_with_children(self):
        child = MenuItem(page="c1")
        group = MenuItem(description="Group", items=[child])
        flat = _flatten([group])
        assert len(flat) == 2
        assert flat[0][1] is False  # group header, not a child
        assert flat[1][1] is True   # child item

    def test_separator_passthrough(self):
        sep = MenuItem(is_separator=True)
        flat = _flatten([sep])
        assert len(flat) == 1
        assert flat[0][1] is False

    def test_mixed(self):
        items = [
            MenuItem(page="p1"),
            MenuItem(is_separator=True),
            MenuItem(description="G", items=[MenuItem(page="c1"), MenuItem(page="c2")]),
        ]
        flat = _flatten(items)
        # p1, sep, group-header, c1, c2
        assert len(flat) == 5


class TestMenuResolve:
    def test_empty_items_returns_empty(self):
        menu = MenuComponent(items=[], tokens={})
        assert menu.resolve(_cell()) == []

    def test_creates_button_per_leaf_item(self):
        items = [MenuItem(page="p1"), MenuItem(page="p2"), MenuItem(page="p3")]
        page_id_map = {"p1": _VALID_ID, "p2": "b" * 20, "p3": "c" * 20}
        menu = MenuComponent(items=items, tokens={}, page_id_map=page_id_map)
        visuals = menu.resolve(_cell())
        btn_visuals = [v for v in visuals if v.visual_type == "actionButton"]
        assert len(btn_visuals) >= 3

    def test_separator_creates_shape(self):
        items = [MenuItem(is_separator=True)]
        menu = MenuComponent(items=items, tokens={})
        visuals = menu.resolve(_cell())
        shape_visuals = [v for v in visuals if v.visual_type == "shape"]
        assert len(shape_visuals) >= 1

    def test_all_visuals_have_positive_width(self):
        items = [MenuItem(page="p1"), MenuItem(is_separator=True), MenuItem(page="p2")]
        page_id_map = {"p1": _VALID_ID, "p2": "b" * 20}
        menu = MenuComponent(items=items, tokens={}, page_id_map=page_id_map)
        visuals = menu.resolve(_cell())
        assert all(v.position.width > 0 for v in visuals)


class TestSlotCell:
    def _menu(self, items, orientation="vertical", tokens=None):
        return MenuComponent(items=items, orientation=orientation, tokens=tokens or {"menu": {"item_height": 48}})

    def test_slot_cell_vertical_y_grows(self):
        items = [MenuItem(page="p1"), MenuItem(page="p2")]
        menu = self._menu(items)
        flat = _flatten(items)
        slot_heights = menu._slot_heights(flat)
        s0 = menu._slot_cell(_cell(), 0, slot_heights, False)
        s1 = menu._slot_cell(_cell(), 1, slot_heights, False)
        assert s0.y == 0
        assert pytest.approx(s1.y, abs=0.01) == 48.0

    def test_slot_cell_horizontal_x_grows(self):
        items = [MenuItem(page="p1"), MenuItem(page="p2")]
        menu = self._menu(items, orientation="horizontal")
        flat = _flatten(items)
        slot_heights = menu._slot_heights(flat)
        c = _cell(w=200, h=48)
        s0 = menu._slot_cell(c, 0, slot_heights, False)
        s1 = menu._slot_cell(c, 1, slot_heights, False)
        assert s0.x == 0
        assert pytest.approx(s1.x, abs=0.01) == 100.0  # 200 / 2

    def test_child_indent_applied_vertical(self):
        child = MenuItem(page="c1")
        group = MenuItem(description="G", items=[child])
        menu = self._menu([group])
        flat = _flatten([group])
        slot_heights = menu._slot_heights(flat)
        # slot 0 = group header (not child), slot 1 = child
        s_header = menu._slot_cell(_cell(), 0, slot_heights, False)
        s_child = menu._slot_cell(_cell(), 1, slot_heights, True)
        assert s_child.x > s_header.x  # child is indented
