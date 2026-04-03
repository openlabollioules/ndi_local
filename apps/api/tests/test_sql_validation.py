"""Tests for SQL validation (read-only safety checks)."""

import pytest

from ndi_api.services.sql_validation import categorize_error, validate_sql_readonly


class TestValidateSqlReadonly:
    """validate_sql_readonly must reject any write operation."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM t",
            "SELECT a, b FROM t WHERE x = 1",
            "WITH cte AS (SELECT 1) SELECT * FROM cte",
            "  SELECT 1  ",
        ],
    )
    def test_valid_selects(self, sql):
        ok, err = validate_sql_readonly(sql)
        assert ok, f"Should be valid: {sql!r}, got error: {err}"

    @pytest.mark.parametrize(
        "keyword",
        [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
        ],
    )
    def test_forbidden_keywords(self, keyword):
        sql = f"{keyword} TABLE t"
        ok, err = validate_sql_readonly(sql)
        assert not ok
        assert keyword in err

    def test_empty_query(self):
        ok, err = validate_sql_readonly("")
        assert not ok
        assert "vide" in err.lower()

    def test_none_query(self):
        ok, err = validate_sql_readonly(None)  # type: ignore[arg-type]
        assert not ok

    def test_starts_with_explain(self):
        ok, err = validate_sql_readonly("EXPLAIN SELECT 1")
        assert not ok


class TestCategorizeError:
    def test_column_not_found(self):
        hint = categorize_error("no such column: foo")
        assert "colonne" in hint.lower()

    def test_table_not_found(self):
        hint = categorize_error("Table 'xyz' not found")
        assert "table" in hint.lower()

    def test_syntax_error(self):
        hint = categorize_error("syntax error near 'SELEC'")
        assert "syntaxe" in hint.lower()

    def test_generic_error(self):
        hint = categorize_error("something unexpected")
        assert hint  # non-empty
