"""Conformity analysis service — pre-filters with Python, then uses LLM for semantic rules.

Supports:
- Enum validation (allowed values)
- Format validation (regex)
- Range validation (min/max)
- Uniqueness check (duplicates)
- Completeness check (required if condition)
- Semantic coherence (LLM-based, batched)
"""

from __future__ import annotations

import json
import logging
import re

from ndi_api.services.llm import get_llm, strip_thinking
from ndi_api.settings import settings

logger = logging.getLogger("ndi.conformity")

# Rough estimate: 1 row ≈ 80 tokens for 10 columns
_TOKENS_PER_ROW = 80
_PROMPT_OVERHEAD = 3000  # tokens for instructions + rules
_MAX_EXAMPLES_PER_RULE = 10


def _estimate_batch_size() -> int:
    """Estimate how many rows fit in one LLM call."""
    available = settings.llm_context_length - _PROMPT_OVERHEAD
    return max(50, available // _TOKENS_PER_ROW)


# ═══════════════════════════════════════════════════════════════════════
# Python pre-filters (fast, exhaustive)
# ═══════════════════════════════════════════════════════════════════════


def check_enum(
    rows: list[dict],
    column: str,
    allowed: list[str],
) -> list[dict]:
    """Check that column only contains allowed values."""
    violations = []
    allowed_lower = {v.lower().strip() for v in allowed}
    for i, row in enumerate(rows):
        val = row.get(column)
        if val is None or str(val).strip() == "":
            continue  # nulls handled by completeness rules
        if str(val).strip().lower() not in allowed_lower:
            violations.append(
                {
                    "row_index": i,
                    "column": column,
                    "current_value": val,
                    "expected": f"Une de : {', '.join(allowed)}",
                    "severity": "error",
                }
            )
    return violations


def check_format(
    rows: list[dict],
    column: str,
    pattern: str,
) -> list[dict]:
    """Check that column matches a regex pattern."""
    violations = []
    try:
        regex = re.compile(pattern)
    except re.error:
        return [{"error": f"Regex invalide : {pattern}"}]

    for i, row in enumerate(rows):
        val = row.get(column)
        if val is None or str(val).strip() == "":
            continue
        if not regex.match(str(val).strip()):
            violations.append(
                {
                    "row_index": i,
                    "column": column,
                    "current_value": val,
                    "expected": f"Format : {pattern}",
                    "severity": "warning",
                }
            )
    return violations


def check_range(
    rows: list[dict],
    column: str,
    min_val: float | None = None,
    max_val: float | None = None,
) -> list[dict]:
    """Check that numeric column is within bounds."""
    violations = []
    for i, row in enumerate(rows):
        val = row.get(column)
        if val is None:
            continue
        try:
            num = float(val)
        except (ValueError, TypeError):
            continue
        if min_val is not None and num < min_val:
            violations.append(
                {
                    "row_index": i,
                    "column": column,
                    "current_value": val,
                    "expected": f">= {min_val}",
                    "severity": "error",
                }
            )
        if max_val is not None and num > max_val:
            violations.append(
                {
                    "row_index": i,
                    "column": column,
                    "current_value": val,
                    "expected": f"<= {max_val}",
                    "severity": "error",
                }
            )
    return violations


def check_uniqueness(rows: list[dict], column: str) -> list[dict]:
    """Check for duplicate values."""
    seen: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        val = row.get(column)
        if val is None:
            continue
        key = str(val).strip().lower()
        seen.setdefault(key, []).append(i)

    violations = []
    for val_key, indices in seen.items():
        if len(indices) > 1:
            for idx in indices[1:]:  # first occurrence is OK
                violations.append(
                    {
                        "row_index": idx,
                        "column": column,
                        "current_value": rows[idx].get(column),
                        "expected": "Valeur unique",
                        "severity": "warning",
                    }
                )
    return violations


def check_completeness(
    rows: list[dict],
    column: str,
    condition_col: str | None = None,
    condition_val: str | None = None,
) -> list[dict]:
    """Check that column is not null/empty, optionally conditioned."""
    violations = []
    for i, row in enumerate(rows):
        # Check condition if specified
        if condition_col and condition_val:
            cond = row.get(condition_col)
            if cond is None or str(cond).strip().lower() != condition_val.lower():
                continue  # condition not met, skip

        val = row.get(column)
        if val is None or str(val).strip() == "":
            violations.append(
                {
                    "row_index": i,
                    "column": column,
                    "current_value": None,
                    "expected": "Non vide" + (f" (quand {condition_col}={condition_val})" if condition_col else ""),
                    "severity": "error",
                }
            )
    return violations


# ═══════════════════════════════════════════════════════════════════════
# LLM-based semantic check (batched)
# ═══════════════════════════════════════════════════════════════════════


def check_semantic_batch(
    rows: list[dict],
    rules: list[str],
    columns: list[str] | None = None,
) -> list[dict]:
    """Use LLM to check semantic/coherence rules on data in batches.

    Returns a list of violations with suggested fixes.
    """
    if not rows or not rules:
        return []

    batch_size = _estimate_batch_size()
    all_violations: list[dict] = []

    # Only send relevant columns to save tokens
    if columns:
        filtered_rows = [{k: v for k, v in row.items() if k in columns} for row in rows]
    else:
        filtered_rows = rows

    for batch_start in range(0, len(filtered_rows), batch_size):
        batch = filtered_rows[batch_start : batch_start + batch_size]
        batch_with_idx = [{"_row": batch_start + i, **row} for i, row in enumerate(batch)]

        rules_text = "\n".join(f"- {r}" for r in rules)
        prompt = (
            "Tu es un auditeur de conformité de données.\n\n"
            f"RÈGLES À VÉRIFIER :\n{rules_text}\n\n"
            f"DONNÉES ({len(batch)} lignes, champ _row = numéro de ligne) :\n"
            f"{json.dumps(batch_with_idx, ensure_ascii=False)}\n\n"
            "Pour chaque violation trouvée, retourne un JSON array :\n"
            "```json\n"
            '[{"row_index": <_row>, "column": "<col>", "current_value": "<val>", '
            '"expected": "<description>", "severity": "error|warning", '
            '"suggested_fix": "<valeur corrigée ou null>"}]\n'
            "```\n"
            "Si aucune violation, retourne `[]`.\n"
            "Retourne UNIQUEMENT le JSON, sans explication."
        )

        try:
            raw = strip_thinking(get_llm().invoke(prompt).content)
            # Extract JSON from response
            json_match = re.search(r"\[.*\]", raw, re.DOTALL)
            if json_match:
                batch_violations = json.loads(json_match.group())
                all_violations.extend(batch_violations)
        except Exception as e:
            logger.warning("Semantic check batch %d failed: %s", batch_start, e)

    return all_violations


# ═══════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════


def run_conformity_audit(
    rows: list[dict],
    rules_text: str,
    table_name: str = "",
) -> dict:
    """Run a full conformity audit.

    Args:
        rows: All data rows
        rules_text: Rules in natural language (one per line or paragraph)
        table_name: Table name for reporting

    Returns:
        Dict with conformity report structure
    """
    total_rows = len(rows)
    all_violations: list[dict] = []
    rule_results: list[dict] = []

    # Parse rules — send everything to LLM for semantic analysis
    # The LLM is better at understanding natural language rules than trying to
    # programmatically parse them into enum/format/range types.
    rules = [r.strip() for r in rules_text.strip().split("\n") if r.strip() and not r.strip().startswith("#")]

    if not rules:
        rules = [rules_text.strip()]

    logger.info("Conformity audit: %d rules on %d rows (table=%s)", len(rules), total_rows, table_name)

    # Run LLM semantic check on all rules at once
    violations = check_semantic_batch(rows, rules)
    all_violations.extend(violations)

    # Group violations by rule description
    rule_violation_counts: dict[str, int] = {}
    for v in violations:
        rule_desc = v.get("expected", "Règle non spécifiée")
        rule_violation_counts[rule_desc] = rule_violation_counts.get(rule_desc, 0) + 1

    for rule in rules:
        # Count violations that mention this rule
        count = sum(1 for v in violations if rule.lower()[:30] in v.get("expected", "").lower())
        rule_results.append(
            {
                "rule": rule,
                "status": "violated" if count > 0 else "ok",
                "violation_count": count,
                "examples": [v for v in violations if rule.lower()[:30] in v.get("expected", "").lower()][
                    :_MAX_EXAMPLES_PER_RULE
                ],
            }
        )

    # Conformity score
    violated_rows = len({v["row_index"] for v in all_violations})
    score = round((1 - violated_rows / max(total_rows, 1)) * 100, 1) if total_rows else 0

    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "rules_checked": len(rules),
        "total_violations": len(all_violations),
        "conformity_score": score,
        "rule_results": rule_results,
        "corrections": all_violations,
        "corrected_file_available": any(v.get("suggested_fix") for v in all_violations),
    }


def apply_corrections(
    rows: list[dict],
    corrections: list[dict],
) -> list[dict]:
    """Apply corrections to the data and return the corrected rows."""
    corrected = [dict(row) for row in rows]  # deep copy

    for fix in corrections:
        idx = fix.get("row_index")
        col = fix.get("column")
        new_val = fix.get("suggested_fix")
        if idx is not None and col and new_val is not None and idx < len(corrected):
            corrected[idx][col] = new_val

    return corrected
