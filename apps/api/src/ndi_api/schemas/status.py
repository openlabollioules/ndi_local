from pydantic import BaseModel


class IndexStatus(BaseModel):
    indexed: int
