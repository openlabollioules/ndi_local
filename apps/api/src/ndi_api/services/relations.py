from __future__ import annotations

import json
from pathlib import Path

from ndi_api.settings import settings


def _relations_path() -> Path:
    return Path(settings.data_dir) / "relations.json"


def load_relations() -> list[dict]:
    path = _relations_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_relations(relations: list[dict]) -> None:
    path = _relations_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(relations, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_relation(payload: dict) -> list[dict]:
    relations = load_relations()
    key = (
        payload["from_table"],
        payload["from_column"],
        payload["to_table"],
        payload["to_column"],
        payload.get("relation_type", "foreign_key"),
    )
    filtered = [
        rel
        for rel in relations
        if (
            rel["from_table"],
            rel["from_column"],
            rel["to_table"],
            rel["to_column"],
            rel.get("relation_type", "foreign_key"),
        )
        != key
    ]
    filtered.append(payload)
    save_relations(filtered)
    return filtered
