"""Heuristic chart suggestion engine.

Analyzes query result rows to suggest an appropriate chart configuration.
Zero LLM calls — pure heuristics for zero added latency.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict


class ChartConfig(TypedDict, total=False):
    type: str  # bar | line | pie | area | scatter | radar
    xKey: str
    yKeys: list[str]
    title: str


_DATE_RE = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}"  # 2024-01-15 …
    r"|^\d{2}[-/]\d{2}[-/]\d{4}"  # 15/01/2024 …
)

_DATE_KEYWORDS = {"date", "jour", "mois", "annee", "année", "semaine", "period", "time", "timestamp"}

_COUNT_KEYWORDS = {"count", "nb", "nombre", "total", "sum", "somme", "effectif", "freq"}


def _is_numeric(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.replace(",", "."))
            return True
        except (ValueError, AttributeError):
            return False
    return False


def _is_date_like(value: Any) -> bool:
    if value is None:
        return False
    return bool(_DATE_RE.match(str(value).strip()))


def _classify_columns(
    rows: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    """Return (numeric_cols, date_cols, categorical_cols) from a sample of rows."""
    if not rows:
        return [], [], []

    sample = rows[:50]
    cols = list(rows[0].keys())
    numeric_cols: list[str] = []
    date_cols: list[str] = []
    categorical_cols: list[str] = []

    for col in cols:
        non_null = [r[col] for r in sample if r.get(col) is not None]
        if not non_null:
            continue

        num_count = sum(1 for v in non_null if _is_numeric(v))
        date_count = sum(1 for v in non_null if _is_date_like(v))
        col_lower = col.lower()

        if date_count > len(non_null) * 0.6 or col_lower in _DATE_KEYWORDS:
            date_cols.append(col)
        elif num_count > len(non_null) * 0.7:
            numeric_cols.append(col)
        else:
            categorical_cols.append(col)

    return numeric_cols, date_cols, categorical_cols


def _count_unique(rows: list[dict[str, Any]], col: str) -> int:
    return len({str(r.get(col, "")) for r in rows})


def suggest_chart(
    rows: list[dict[str, Any]],
    question: str = "",
) -> ChartConfig | None:
    """Suggest a chart configuration based on row data and optional question context.

    Returns None when data is not suitable for charting.
    """
    if not rows or len(rows) < 2:
        return None

    cols = list(rows[0].keys())
    if len(cols) < 2:
        return None

    numeric_cols, date_cols, cat_cols = _classify_columns(rows)
    q_lower = question.lower()

    # --- Time series → line or area ---
    if date_cols and numeric_cols:
        chart_type = "area" if any(k in q_lower for k in ("évolution", "tendance", "trend", "cumul")) else "line"
        return ChartConfig(
            type=chart_type,
            xKey=date_cols[0],
            yKeys=numeric_cols[:3],
            title=_auto_title(question, chart_type),
        )

    # --- Radar: categorical axis + >=3 numeric axes (profile / multi-criteria) ---
    if cat_cols and len(numeric_cols) >= 3:
        return ChartConfig(
            type="radar",
            xKey=cat_cols[0],
            yKeys=numeric_cols[:6],
            title=_auto_title(question, "radar"),
        )

    # --- Distribution / proportions → pie (<=8 categories, 1 numeric) ---
    if cat_cols and numeric_cols:
        first_cat = cat_cols[0]
        n_unique = _count_unique(rows, first_cat)
        is_proportion = any(k in q_lower for k in ("répartition", "proportion", "distribution", "part", "pourcentage"))

        if (n_unique <= 8 and len(rows) <= 15) or is_proportion:
            return ChartConfig(
                type="pie",
                xKey=first_cat,
                yKeys=[numeric_cols[0]],
                title=_auto_title(question, "pie"),
            )

    # --- Scatter: 2+ numeric columns, no good categorical axis ---
    if len(numeric_cols) >= 2 and not cat_cols and not date_cols:
        return ChartConfig(
            type="scatter",
            xKey=numeric_cols[0],
            yKeys=[numeric_cols[1]],
            title=_auto_title(question, "scatter"),
        )

    # --- Default: bar chart (categorical + numeric) ---
    if cat_cols and numeric_cols:
        return ChartConfig(
            type="bar",
            xKey=cat_cols[0],
            yKeys=numeric_cols[:3],
            title=_auto_title(question, "bar"),
        )

    # --- Fallback: first col as x, remaining numeric as y → bar ---
    if numeric_cols and len(cols) >= 2:
        x_candidate = next((c for c in cols if c not in numeric_cols), cols[0])
        y_candidates = [c for c in numeric_cols if c != x_candidate][:3]
        if y_candidates:
            return ChartConfig(
                type="bar",
                xKey=x_candidate,
                yKeys=y_candidates,
                title=_auto_title(question, "bar"),
            )

    return None


def _auto_title(question: str, chart_type: str) -> str:
    if question:
        title = question[:80]
        if len(question) > 80:
            title += "..."
        return title
    labels = {
        "bar": "Diagramme en barres",
        "line": "Courbe",
        "pie": "Répartition",
        "area": "Évolution",
        "scatter": "Nuage de points",
        "radar": "Radar",
    }
    return labels.get(chart_type, "Graphique")
