from src.grid.schema import (
    Canvas, ColConfig, ColSpec, LayoutSpec, PageSpec, RowSpec,
)
from src.grid.info_table import (
    ICON_MEASURE, TABLE_NAME, build_config_tmdl, build_info_html, collect_info,
    info_column, register_config_in_model,
)


def _layout(cols: list[ColSpec]) -> LayoutSpec:
    return LayoutSpec(
        report_name="r", package=None, canvas=Canvas(),
        pages=[PageSpec(id="p", display_name="P", rows=[RowSpec(id="r0", height=100, cols=cols)])],
    )


class TestBuildInfoHtml:
    def test_inclui_titulo_e_descricao(self):
        html = build_info_html("Titulo", "Corpo da descricao")
        assert "Titulo" in html and "Corpo da descricao" in html
        assert html.startswith("<div") and html.rstrip().endswith("</div>")
        # layout minimalista: título em negrito, sem header colorido/borda/ícone
        assert "font-weight:600" in html
        assert "#E6E6E6" not in html and "border:1px" not in html
        assert "box-shadow" not in html and "&#8505;" not in html

    def test_sem_titulo_so_descricao(self):
        html = build_info_html("", "Somente a descricao")
        assert "Somente a descricao" in html
        assert "font-weight:600" not in html  # sem título => sem heading


class TestCollectInfo:
    def test_so_entra_col_com_info(self):
        cols = [
            ColSpec(span=6, name="v1", config=ColConfig(title="Titulo V1", info="descricao um")),
            ColSpec(span=6, name="v2", config=ColConfig(title="T2")),  # sem info -> ignorado
            ColSpec(span=6, name="v3"),  # sem config -> ignorado
        ]
        items = collect_info(_layout(cols))
        assert [t[0] for t in items] == ["v1"]
        html = {t[0]: t[1] for t in items}["v1"]
        # título do modal = título do visual; corpo = info
        assert "Titulo V1" in html and "descricao um" in html
        assert all(t[2] > 0 for t in items)  # altura estimada presente

    def test_ignora_col_sem_name(self):
        cols = [ColSpec(span=12, config=ColConfig(title="x", info="y"))]
        assert collect_info(_layout(cols)) == []

    def test_ignora_col_sem_info(self):
        cols = [ColSpec(span=6, name="v1", config=ColConfig(title="só título"))]
        assert collect_info(_layout(cols)) == []


class TestBuildConfigTmdl:
    def test_icon_e_uma_coluna_por_visual(self):
        items = [("v1", "<div>a</div>"), ("v2", "<div>b</div>")]
        tmdl = build_config_tmdl(items)
        assert f"measure {ICON_MEASURE}" in tmdl
        assert f"column {info_column('v1')}" in tmdl
        assert f"column {info_column('v2')}" in tmdl
        assert f"table {TABLE_NAME}" in tmdl and f"partition {TABLE_NAME} = m" in tmdl

    def test_escapa_aspas_no_html(self):
        tmdl = build_config_tmdl([("v1", 'x "y" z')])
        assert '""y""' in tmdl  # aspas duplas escapadas no literal M


class TestRegisterConfigInModel:
    _MODEL = (
        "model Model\n\tculture: pt-BR\n\n"
        '\tannotation PBI_QueryOrder = ["DIM_A","FATO_B"]\n\n'
        "ref table DIM_A\nref table FATO_B\n"
    )

    def test_adiciona_ref_e_query_order(self):
        out = register_config_in_model(self._MODEL)
        assert f"ref table {TABLE_NAME}" in out
        assert f'"{TABLE_NAME}"' in out
        assert "ref table DIM_A" in out and "ref table FATO_B" in out

    def test_idempotente(self):
        once = register_config_in_model(self._MODEL)
        twice = register_config_in_model(once)
        assert once == twice
        assert once.count(f"ref table {TABLE_NAME}") == 1
        assert once.count(f'"{TABLE_NAME}"') == 1

    def test_sem_query_order_so_adiciona_ref(self):
        model = "model M\n\nref table DIM_A\n"
        out = register_config_in_model(model)
        assert f"ref table {TABLE_NAME}" in out
        assert "PBI_QueryOrder" not in out