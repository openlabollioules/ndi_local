from pydantic import BaseModel


class RelationPatch(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: str = "foreign_key"


class Relation(RelationPatch):
    pass
