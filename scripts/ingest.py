import logging
from app.db.postgres.base import SessionLocal
from app.services import docs_ingester

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    session = SessionLocal()
    try:
        docs_ingester.ingest_all(session)
        logger.info("Ingestion completed successfully.")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
    finally:
        session.close()
