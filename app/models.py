from typing import List, Optional

from pydantic import BaseModel


class PostSummary(BaseModel):
    id: str
    slug: str
    title: Optional[str] = None
    summary: Optional[str] = None
    publishedAt: Optional[str] = None
    tags: List[str] = []


class PostDetail(BaseModel):
    id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    image: Optional[str] = None
    publishedAt: Optional[str] = None
    tags: List[str] = []
    content: str  # Markdown content without frontmatter
