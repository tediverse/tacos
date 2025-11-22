import uuid
from typing import Any, Dict

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class DocResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str | None = None
    title: str | None = None
    content: str | None = None
    doc_metadata: Dict[str, Any] | None = None
    similarity: float = Field(
        ...,
        ge=0,
        le=1,
        description="The cosine similarity score between the query and the document.",
    )
