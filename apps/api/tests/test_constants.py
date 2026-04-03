"""Tests for shared constants and normalization utilities."""

from ndi_api.constants import (
    ALLOWED_SQL_KEYWORDS,
    FORBIDDEN_SQL_KEYWORDS,
    deduplicate_columns,
    normalize_column_name,
    to_snake,
)


class TestNormalizeColumnName:
    def test_simple(self):
        assert normalize_column_name("MonChamp") == "monchamp"

    def test_strip_prefix_col(self):
        assert normalize_column_name("col_nom") == "nom"

    def test_strip_prefix_field(self):
        assert normalize_column_name("field_age") == "age"

    def test_strip_prefix_champ(self):
        assert normalize_column_name("champ_ville") == "ville"

    def test_special_chars(self):
        result = normalize_column_name("Nom du Client!")
        assert " " not in result
        assert "!" not in result

    def test_leading_trailing_spaces(self):
        assert normalize_column_name("  nom  ") == "nom"

    def test_empty_after_strip(self):
        # "col" alone should return "col" (not empty)
        result = normalize_column_name("col")
        assert result  # non-empty


class TestDeduplicateColumns:
    def test_no_duplicates(self):
        assert deduplicate_columns(["a", "b", "c"]) == ["a", "b", "c"]

    def test_duplicates(self):
        assert deduplicate_columns(["nom", "age", "nom"]) == ["nom", "age", "nom_2"]

    def test_triple(self):
        result = deduplicate_columns(["x", "x", "x"])
        assert result == ["x", "x_2", "x_3"]


class TestToSnake:
    def test_camel(self):
        assert to_snake("HelloWorld") == "helloworld"

    def test_spaces(self):
        assert to_snake("Nom du Client") == "nom_du_client"

    def test_multi_underscores(self):
        assert to_snake("a___b") == "a_b"


class TestKeywordSets:
    def test_no_overlap(self):
        overlap = ALLOWED_SQL_KEYWORDS & FORBIDDEN_SQL_KEYWORDS
        assert not overlap, f"Keywords in both sets: {overlap}"

    def test_select_allowed(self):
        assert "SELECT" in ALLOWED_SQL_KEYWORDS

    def test_drop_forbidden(self):
        assert "DROP" in FORBIDDEN_SQL_KEYWORDS
