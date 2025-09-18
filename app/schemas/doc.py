import uuid
from typing import List, Dict, Any
from pydantic import BaseModel

class DocSchema(BaseModel):
    id: uuid.UUID
    slug: str | None = None
    title: str | None = None
    content: str | None = None
    doc_metadata: Dict[str, Any] | None = None
    embedding: List[float] | None = None

    class Config:
        from_attributes = True