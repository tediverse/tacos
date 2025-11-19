from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.postgres.base import Base


class PostView(Base):
    __tablename__ = "post_views"

    slug = Column(String(512), primary_key=True)
    view_count = Column(Integer, nullable=False, server_default="0")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
