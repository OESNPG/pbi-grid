from src.components.footer import FooterComponent
from src.grid.schema import Cell


def _cell(w=1280, h=80):
    return Cell(x=0, y=0, width=w, height=h, z=1000)


class TestFooterSmoke:
    def test_returns_nonempty(self):
        footer = FooterComponent(tokens={})
        visuals = footer.resolve(_cell())
        assert len(visuals) > 0

    def test_all_positive_width(self):
        footer = FooterComponent(tokens={})
        visuals = footer.resolve(_cell())
        assert all(v.position.width > 0 for v in visuals)

    def test_has_background_shape(self):
        footer = FooterComponent(tokens={"footer": {"background_color": "#071D41"}})
        visuals = footer.resolve(_cell())
        shapes = [v for v in visuals if v.visual_type == "shape"]
        assert len(shapes) >= 1

    def test_legal_text_adds_visual(self):
        without = FooterComponent(tokens={})
        with_legal = FooterComponent(legal="Legal notice text", tokens={})
        assert len(with_legal.resolve(_cell())) > len(without.resolve(_cell()))

    def test_divider_adds_shape(self):
        tokens = {"footer": {"divider_color": "#333333", "divider_height": 4}}
        footer = FooterComponent(tokens=tokens)
        visuals = footer.resolve(_cell())
        shapes = [v for v in visuals if v.visual_type == "shape"]
        assert len(shapes) >= 2  # background + divider
