from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.postgres.base import Base


class CouchDBChanges(Base):
    __tablename__ = "couchdb_changes"

    id = Column(Integer, primary_key=True)
    last_seq = Column(String, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
