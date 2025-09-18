import sys

from app.db.couchdb import parser
from app.db.postgres import SessionLocal
from app.services import docs_ingester


def ingest_all():
    session = SessionLocal()
    docs_ingester.ingest_all(session, parser)
    session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest.py [all]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd in ("all"):
        ingest_all()
        print("Ingestion completed.")
    else:
        print(f"Unknown command {cmd}")
