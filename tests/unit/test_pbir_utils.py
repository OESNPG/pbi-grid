from src.pbir_utils import make_id, literal, hex_color, theme_color


class TestMakeId:
    def test_passthrough_valid_id(self):
        seed = "a" * 20
        assert make_id(seed) == seed

    def test_hash_long_seed(self):
        long_seed = "this-is-a-very-long-seed-string-that-exceeds-20-chars"
        result = make_id(long_seed)
        assert len(result) == 20
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        seed = "my-seed"
        assert make_id(seed) == make_id(seed)

    def test_short_non_hex_not_passed_through(self):
        # 20 chars but not all hex — should be hashed
        seed = "zzzzzzzzzzzzzzzzzzzz"
        result = make_id(seed)
        assert len(result) == 20
        assert result != seed


class TestLiteral:
    def test_structure(self):
        result = literal("'x'")
        assert result == {"expr": {"Literal": {"Value": "'x'"}}}

    def test_various_values(self):
        assert literal("true")["expr"]["Literal"]["Value"] == "true"
        assert literal("42D")["expr"]["Literal"]["Value"] == "42D"


class TestHexColor:
    def test_structure(self):
        result = hex_color("#FFF")
        assert result["solid"]["color"]["expr"]["Literal"]["Value"] == "'#FFF'"

    def test_full_hex(self):
        result = hex_color("#1351B4")
        assert "'#1351B4'" in str(result)


class TestThemeColor:
    def test_structure(self):
        result = theme_color(1, 0.5)
        tc = result["solid"]["color"]["expr"]["ThemeDataColor"]
        assert tc["ColorId"] == 1
        assert tc["Percent"] == 0.5

    def test_zero_percent(self):
        result = theme_color(2, 0.0)
        tc = result["solid"]["color"]["expr"]["ThemeDataColor"]
        assert tc["ColorId"] == 2
        assert tc["Percent"] == 0.0
