from pydantic import BaseModel


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    total_count: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool
