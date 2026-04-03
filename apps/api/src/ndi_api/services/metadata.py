from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ndi_api.settings import settings


def _schema_map_path() -> Path:
    return Path(settings.data_dir) / "schema_map.json"


def load_schema_map() -> dict[str, list[dict[str, str]]]:
    path = _schema_map_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_schema_map(schema_map: dict[str, list[dict[str, str]]]) -> None:
    path = _schema_map_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema_map, ensure_ascii=False, indent=2), encoding="utf-8")


def update_schema_map(
    table: str,
    original_columns: Iterable[str],
    normalized_columns: Iterable[str],
) -> None:
    schema_map = load_schema_map()
    entries = [
        {"original": original, "normalized": normalized}
        for original, normalized in zip(original_columns, normalized_columns, strict=False)
    ]
    schema_map[table] = entries
    save_schema_map(schema_map)


def batch_update_schema_map(
    updates: dict[str, tuple[list[str], list[str]]],
) -> None:
    """Update multiple tables in a single read/write cycle."""
    schema_map = load_schema_map()
    for table, (originals, normalized) in updates.items():
        schema_map[table] = [{"original": o, "normalized": n} for o, n in zip(originals, normalized, strict=False)]
    save_schema_map(schema_map)
