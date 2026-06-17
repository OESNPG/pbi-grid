from src.grid.schema import (
    Canvas, ColConfig, ColSpec, InfoSpec, LayoutSpec, PageSpec, RowSpec,
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
    def test_inclui_titulo_descricao_rodape(self):
        html = build_info_html("Titulo", "Corpo da descricao", "Rodape")
        assert "Titulo" in html and "Corpo da descricao" in html and "Rodape" in html
        assert html.startswith("<div") and html.rstrip().endswith("</div>")
        assert "border:1px" in html  # card com moldura quando há header/footer

    def test_sem_titulo_e_rodape_colapsa_para_corpo(self):
        html = build_info_html("", "Somente a descricao", "")
        assert "Somente a descricao" in html
        # sem header (#E6E6E6), sem ícone e sem moldura/sombra
        assert "#E6E6E6" not in html
        assert "&#8505;" not in html
        assert "border:1px" not in html and "box-shadow" not in html

    def test_apenas_titulo_vazio_mantem_rodape_e_moldura(self):
        html = build_info_html("", "Corpo", "Rodape")
        assert "Rodape" in html and "border:1px" in html


class TestCollectInfo:
    def test_uma_entrada_por_col_com_config(self):
        cols = [
            ColSpec(span=6, name="v1", config=ColConfig(info=InfoSpec(title="A", description="da"))),
            ColSpec(span=6, name="v2", config=ColConfig(title="T2")),  # info.title vazio -> usa title
            ColSpec(span=6, name="v3"),  # sem config -> ignorado
        ]
        items = collect_info(_layout(cols))
        names = [t[0] for t in items]
        assert names == ["v1", "v2"]
        htmls = {t[0]: t[1] for t in items}
        heights = {t[0]: t[2] for t in items}
        # fallback do título do modal: info.title ou title do visual
        assert "A" in htmls["v1"]
        assert "T2" in htmls["v2"]
        assert all(h > 0 for h in heights.values())  # altura estimada presente

    def test_ignora_col_sem_name(self):
        cols = [ColSpec(span=12, config=ColConfig(title="x"))]
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