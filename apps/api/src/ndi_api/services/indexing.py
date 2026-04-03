from __future__ import annotations

import json
import logging
from collections.abc import Callable

from ndi_api.plugins.manager import get_plugin_manager
from ndi_api.services.llm import get_indexing_llm
from ndi_api.services.metadata import load_schema_map
from ndi_api.services.monitoring import log_indexing_complete
from ndi_api.services.vector_store import upsert_documents

_logger = logging.getLogger("ndi.indexing")


def _generate_table_descriptions_batch(
    table: str,
    columns: list[dict],
    sample_data: dict[str, list] | None,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict[str, str]:
    """Generate descriptions for all columns/fields in ONE LLM call (batch mode).

    Args:
        table: Table/collection name
        columns: List of {"name": str, "type": str}
        sample_data: Optional sample values per column
        on_progress: Progress callback

    Returns:
        Dict mapping column name to description
    """
    plugin = get_plugin_manager().get_plugin()
    is_nosql = plugin.mode == "nosql"

    columns_text = "\n".join(
        [
            f"- {col['name']} (type: {col['type']})"
            + (
                f" - exemples: {', '.join(map(str, sample_data.get(col['name'], [])[:3]))}"
                if sample_data and col["name"] in sample_data
                else ""
            )
            for col in columns
        ]
    )

    if is_nosql:
        prompt = f"""Tu es un assistant data expert. Décris chaque champ de la collection suivante en UNE SEULE PHRASE pour aider à écrire des requêtes JSON.

Collection: {table}

Champs:
{columns_text}

Réponds STRICTEMENT au format JSON suivant (uniquement l'objet JSON, pas de markdown):
{{
  "column_descriptions": {{
    "nom_champ_1": "description courte et précise",
    "nom_champ_2": "description courte et précise"
  }}
}}

Règles:
- Une description par champ
- Sois concise (10-15 mots max)
- Mentionne l'unité si évidente (€, kg, date, etc.)
- Les champs peuvent être imbriqués (ex: client.adresse.ville)
- Pas de JOINs en NoSQL - les données liées sont dans le même document"""
    else:
        prompt = f"""Tu es un assistant data expert. Décris chaque colonne de la table suivante en UNE SEULE PHRASE pour aider à écrire des requêtes SQL.

Table: {table}

Colonnes:
{columns_text}

Réponds STRICTEMENT au format JSON suivant (uniquement l'objet JSON, pas de markdown):
{{
  "column_descriptions": {{
    "nom_colonne_1": "description courte et précise",
    "nom_colonne_2": "description courte et précise"
  }}
}}

Règles:
- Une description par colonne
- Sois concise (10-15 mots max)
- Mentionne l'unité si évidente (€, kg, date, etc.)
- Si la colonne semble être une clé étrangère (se termine par _id), mentionne la table référencée"""

    if on_progress:
        entity_type = "champs" if is_nosql else "colonnes"
        on_progress("dictionary", f"Génération descriptions pour {table} ({len(columns)} {entity_type})")

    try:
        from ndi_api.services.llm import strip_thinking

        response = strip_thinking(get_indexing_llm().invoke(prompt).content)

        # Extract JSON from response (handle markdown code blocks)
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())
        descriptions = data.get("column_descriptions", {})

        # Ensure all columns have descriptions
        entity_label = "Champ" if is_nosql else "Colonne"
        return {
            col["name"]: descriptions.get(col["name"], f"{entity_label} {col['name']} de type {col['type']}.")
            for col in columns
        }
    except Exception:
        # Fallback: generic descriptions
        entity_label = "Champ" if is_nosql else "Colonne"
        return {col["name"]: f"{entity_label} {col['name']} de type {col['type']}." for col in columns}


def _get_column_stats(table: str, columns: list[str]) -> dict[str, dict]:
    """Get statistics for all columns using plugin."""
    stats: dict[str, dict] = {}
    plugin = get_plugin_manager().get_plugin()

    if not columns:
        return stats

    try:
        table_stats = plugin.get_table_stats(table)
        if "error" in table_stats:
            return stats

        column_stats = table_stats.get("column_stats", {})
        for col in columns:
            if col in column_stats:
                col_stat = column_stats[col]
                stats[col] = {
                    "cardinality": col_stat.get("unique_values", 0) / max(col_stat.get("non_null", 1), 1),
                    "unique_count": col_stat.get("unique_values", 0),
                    "total_count": table_stats.get("row_count", 0),
                }
    except Exception:
        pass

    return stats


def _get_sample_data(table: str, columns: list[str], limit: int = 3) -> dict[str, list]:
    """Get sample values using plugin."""
    samples: dict[str, list] = {}
    plugin = get_plugin_manager().get_plugin()

    if not columns:
        return samples

    try:
        rows = plugin.get_sample_data(table, limit=limit)
        for col in columns:
            vals = [row.get(col) for row in rows if row.get(col) is not None]
            samples[col] = vals[:limit]
    except Exception:
        pass

    return samples


def index_schema(
    on_progress: Callable[[str, str], None] | None = None,
    include_stats: bool = False,
) -> int:
    """Index schema with batch column description generation.

    Args:
        on_progress: Progress callback
        include_stats: Whether to include column statistics in embeddings
    """
    import time

    start_time = time.time()
    total_llm_calls = [0]

    plugin = get_plugin_manager().get_plugin()
    schema_info = plugin.get_schema()
    schema_map = load_schema_map()
    documents: list[str] = []
    ids: list[str] = []
    metadatas: list[dict] = []

    # Use "collection" for NoSQL, "table" for SQL in documents
    entity_name = "collection" if plugin.mode == "nosql" else "table"

    for table in schema_info.tables:
        table_name = table.name
        columns = [{"name": c.name, "type": c.type} for c in table.columns]
        column_names = [c.name for c in table.columns]
        mapping = schema_map.get(table_name, [])
        alias_text = ", ".join(f"{item['original']} -> {item['normalized']}" for item in mapping)

        # Build table/collection document WITH column types
        cols_with_types = [f"{col['name']} ({col['type']})" for col in columns]

        if plugin.mode == "nosql":
            # NoSQL: emphasize document structure
            doc_text = f"Collection {table_name} avec champs: {', '.join(cols_with_types)}."
            if alias_text:
                doc_text += f" Alias originaux: {alias_text}."
            doc_text += " Les données sont stockées comme documents JSON."
        else:
            # SQL: standard table description
            if alias_text:
                doc_text = (
                    f"Table {table_name} avec colonnes: {', '.join(cols_with_types)}. Alias originaux: {alias_text}."
                )
            else:
                doc_text = f"Table {table_name} avec colonnes: {', '.join(cols_with_types)}."

        documents.append(doc_text)
        ids.append(f"{entity_name}::{table_name}")
        metadatas.append({"type": entity_name, "table": table_name})

        # Get sample data for better descriptions
        sample_data = _get_sample_data(table_name, column_names)

        # Generate ALL column descriptions in ONE LLM call (batch)
        total_llm_calls[0] += 1
        descriptions = _generate_table_descriptions_batch(
            table_name,
            columns,
            sample_data,
            on_progress=on_progress,
        )

        # Get stats if requested
        stats = _get_column_stats(table_name, column_names) if include_stats else {}

        # Create documents for each column/field
        for col in columns:
            col_name = col["name"]
            col_type = col["type"]
            original_names = [item["original"] for item in mapping if item.get("normalized") == col_name]
            alias_suffix = f" (alias: {', '.join(original_names)})" if original_names else ""

            description = descriptions.get(
                col_name, f"{'Champ' if plugin.mode == 'nosql' else 'Colonne'} {col_name} de type {col_type}."
            )

            # Build document with optional stats
            if plugin.mode == "nosql":
                doc_parts = [
                    f"Collection {table_name}, champ {col_name} (type: {col_type}){alias_suffix}.",
                    f"Description: {description}",
                ]
                # NoSQL hint
                doc_parts.append("Peut être un champ imbriqué (ex: client.nom).")
            else:
                doc_parts = [
                    f"Table {table_name}, colonne {col_name} (type: {col_type}){alias_suffix}.",
                    f"Description: {description}",
                ]

            if include_stats and col_name in stats:
                col_stats = stats[col_name]
                if col_stats["unique_count"] > 0:
                    cardinality = col_stats["cardinality"]
                    if cardinality < 0.01:
                        doc_parts.append("Valeur quasi-constante.")
                    elif cardinality > 0.9:
                        doc_parts.append("Valeurs uniques (identifiant).")
                    else:
                        doc_parts.append(f"{col_stats['unique_count']} valeurs distinctes.")

            documents.append(" ".join(doc_parts))
            ids.append(
                f"field::{table_name}::{col_name}" if plugin.mode == "nosql" else f"column::{table_name}::{col_name}"
            )
            metadatas.append(
                {"type": "field" if plugin.mode == "nosql" else "column", "table": table_name, "column": col_name}
            )

    if not documents:
        return 0

    if on_progress:
        on_progress("vector_index", "Indexation sémantique en cours")

    try:
        result = upsert_documents(documents, ids, metadatas)
    except Exception as e:
        _logger.warning("Vector store upsert failed: %s", e, exc_info=True)
        if on_progress:
            on_progress("vector_index_error", f"Erreur d'indexation vectorielle : {e}")
        return 0

    # Log indexing performance
    indexing_duration = time.time() - start_time
    log_indexing_complete(
        duration=indexing_duration,
        table_count=len(schema_info.tables),
        document_count=len(documents),
        llm_calls=total_llm_calls[0],
    )

    return result
