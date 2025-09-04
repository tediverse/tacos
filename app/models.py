from typing import List, Optional

from pydantic import BaseModel, Field


class PostSummary(BaseModel):
    id: str
    slug: str
    title: str
    summary: Optional[str] = None
    image: Optional[str] = None
    publishedAt: Optional[str] = None
    updatedAt: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    readingTime: Optional[str] = None
    draft: bool = False


class PostDetail(PostSummary):
    content: str
