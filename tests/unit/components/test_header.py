from src.components.header import HeaderComponent
from src.grid.schema import Cell


def _cell(w=1280, h=60):
    return Cell(x=0, y=0, width=w, height=h, z=1000)


class TestHeaderSmoke:
    def test_returns_nonempty(self):
        header = HeaderComponent(title="Test Title", tokens={})
        visuals = header.resolve(_cell())
        assert len(visuals) > 0

    def test_all_positive_width(self):
        header = HeaderComponent(title="Test", tokens={})
        visuals = header.resolve(_cell())
        assert all(v.position.width > 0 for v in visuals)

    def test_has_background_shape(self):
        header = HeaderComponent(title="Test", tokens={})
        visuals = header.resolve(_cell())
        types = [v.visual_type for v in visuals]
        assert "shape" in types

    def test_has_title_button(self):
        header = HeaderComponent(title="Test", tokens={})
        visuals = header.resolve(_cell())
        types = [v.visual_type for v in visuals]
        assert "actionButton" in types

    def test_subtitle_creates_extra_text(self):
        no_sub = HeaderComponent(title="T", tokens={})
        with_sub = HeaderComponent(title="T", subtitle="S", tokens={})
        assert len(with_sub.resolve(_cell())) > len(no_sub.resolve(_cell()))
