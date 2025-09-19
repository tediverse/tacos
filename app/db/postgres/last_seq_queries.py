from sqlalchemy.orm import Session

from app.models.couchdb_changes import CouchDBChanges


def get_last_seq(db: Session) -> str:
    offset = db.query(CouchDBChanges).first()
    return offset.last_seq if offset else "now"


def update_last_seq(db: Session, seq: str):
    offset = db.query(CouchDBChanges).first()
    if offset:
        offset.last_seq = seq
    else:
        offset = CouchDBChanges(last_seq=seq)
        db.add(offset)
    db.commit()
