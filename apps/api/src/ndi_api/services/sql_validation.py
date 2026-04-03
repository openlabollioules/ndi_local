"""SQL validation — read-only safety checks.

Extracted from nl_sql.py for reuse and testability.
"""

from __future__ import annotations

import re

import sqlparse
from sqlparse import tokens as T

from ndi_api.constants import FORBIDDEN_SQL_KEYWORDS


def validate_sql_readonly(sql: str) -> tuple[bool, str]:
    """Validate that SQL is read-only and safe to execute.

    Returns:
        (is_valid, error_message)
    """
    if not sql or not sql.strip():
        return False, "Requête SQL vide."

    sql_clean = sql.strip().upper()

    # Check for forbidden keywords
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        pattern = r"\b" + keyword + r"\b"
        if re.search(pattern, sql_clean):
            return False, f"Opération '{keyword}' non autorisée. Seules les requêtes SELECT sont permises."

    # Parse SQL to ensure it starts with SELECT or WITH
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False, "Impossible de parser la requête SQL."

        first_statement = parsed[0]
        first_token = None

        for token in first_statement.tokens:
            if token.ttype not in (T.Whitespace, T.Comment.Single, T.Comment.Multiline):
                if token.ttype in (T.Keyword.DML, T.Keyword.CTE):
                    first_token = token.value.upper()
                elif hasattr(token, "ttype") and token.ttype:
                    first_token = str(token).upper()
                break

        if first_token not in ("SELECT", "WITH"):
            return False, f"Requête doit commencer par SELECT ou WITH (trouvé: {first_token})."

    except Exception:
        if not re.match(r"^\s*(SELECT|WITH)\s+", sql_clean):
            return False, "Requête doit commencer par SELECT ou WITH."

    return True, ""


def categorize_error(error: str) -> str:
    """Categorize SQL execution error and return a hint for correction."""
    err_lower = error.lower()

    if "no such column" in err_lower or "column" in err_lower and "not found" in err_lower:
        return "Colonne inexistante. Vérifie le schéma et utilise les noms exacts."
    if "no such table" in err_lower or "table" in err_lower and "not found" in err_lower:
        return "Table inexistante. Vérifie le schéma."
    if "syntax error" in err_lower:
        return "Erreur de syntaxe SQL. Vérifie la requête."
    if "ambiguous" in err_lower:
        return "Colonne ambiguë. Préfixe avec le nom de table (table.colonne)."
    if "type mismatch" in err_lower or "cast" in err_lower:
        return "Erreur de type. Vérifie les types de colonnes dans le schéma."

    return "Erreur SQL. Corrige la requête en respectant le schéma."
