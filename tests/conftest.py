from src.grid.schema import Canvas, ColSpec, RowSpec, PageSpec


def make_canvas(width=1280, height=720, gutter=4):
    return Canvas(width=width, height=height, gutter=gutter)


def make_col(span, component=None, name=None, visual=None, rowspan=1, height=None, valign="top"):
    return ColSpec(
        span=span, component=component, name=name, visual=visual,
        rowspan=rowspan, height=height, valign=valign,
    )


def make_row(id, height, cols):
    return RowSpec(id=id, height=height, cols=cols)


def make_page(id, rows):
    return PageSpec(id=id, display_name=id, rows=rows)
