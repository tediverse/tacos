import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, UUID, Column, Text

from app.db.postgres import Base


class Doc(Base):
    __tablename__ = "docs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(Text, unique=True, index=True)
    title = Column(Text)
    content = Column(Text)
    doc_metadata = Column("metadata", JSON, key="metadata")
    embedding = Column(Vector(1536))  # adjust
