from sqlalchemy.orm import Session

from app.models.couchdb_changes import CouchDBChanges


class LastSeqRepo:
    """Persistence helper for CouchDB changes feed offsets."""

    def __init__(self, db: Session):
        self.db = db

    def get_last_seq(self) -> str:
        offset = self.db.query(CouchDBChanges).first()
        return offset.last_seq if offset else "now"

    def update_last_seq(self, seq: str) -> None:
        offset = self.db.query(CouchDBChanges).first()
        if offset:
            offset.last_seq = seq
        else:
            offset = CouchDBChanges(last_seq=seq)
            self.db.add(offset)
        self.db.commit()
