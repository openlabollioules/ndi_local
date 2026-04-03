from fastapi import APIRouter

from ndi_api.schemas.relations import Relation, RelationPatch
from ndi_api.services.relations import load_relations, upsert_relation

router = APIRouter(prefix="/relations")


@router.get("", response_model=list[Relation])
async def list_relations() -> list[Relation]:
    return [Relation(**item) for item in load_relations()]


@router.post("", response_model=list[Relation])
async def upsert_relation_route(payload: RelationPatch) -> list[Relation]:
    updated = upsert_relation(payload.model_dump())
    return [Relation(**item) for item in updated]
