import json
import logging
import threading
from typing import Callable

import httpx
from sqlalchemy.orm import Session

from app.db.couchdb import get_couch
from app.db.postgres.base import SessionLocal
from app.models.doc import Doc
from app.repos.last_seq_repo import LastSeqRepo
from app.services.docs_ingester import ingest_doc
from app.settings import Settings, settings

logger = logging.getLogger(__name__)

STOP_LISTENER_EVENT = threading.Event()  # thread-safe shutdown signal


def listen_changes():
    logger.info("CouchDB listener thread started")
    backoff = 1

    while not STOP_LISTENER_EVENT.is_set():
        try:
            couch_db, couch_parser = get_couch()
            with SessionLocal() as db_session:
                seq_repo = LastSeqRepo(db_session)
                last_seq = seq_repo.get_last_seq()
                url = (
                    f"{settings.couchdb_url}/{settings.COUCHDB_DATABASE}/_changes"
                    f"?feed=continuous&include_docs=true&since={last_seq}&heartbeat=true"
                )
                logger.info(f"Connecting to CouchDB _changes since ({last_seq})...")

                with httpx.stream(
                    "GET",
                    url,
                    timeout=httpx.Timeout(
                        connect=5.0, read=None, write=None, pool=None
                    ),
                ) as response:
                    logger.info("Connected, waiting for changes...")
                    backoff = 1  # reset backoff after successful connection

                    for line in response.iter_lines():
                        if STOP_LISTENER_EVENT.is_set():
                            logger.info("Listener stopping...")
                            return

                        # skip heartbeat or empty lines
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            change = json.loads(line)
                            last_seq = change.get("seq", last_seq)
                            seq_repo.update_last_seq(last_seq)
                            process_change(change, db_session, couch_parser)
                        except json.JSONDecodeError:
                            logger.warning(f"Skipping invalid JSON line: {line}")
                        except Exception as e:
                            logger.error(f"Error processing change: {e}")

        except httpx.RequestError as e:
            logger.error(f"HTTP connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected listener error: {e}")

        # Reconnect with exponential backoff
        if not STOP_LISTENER_EVENT.is_set():
            logger.info(f"Reconnecting in {backoff} seconds...")
            STOP_LISTENER_EVENT.wait(backoff)
            backoff = min(backoff * 2, 60)  # cap backoff at 60s


def process_change(
    change: dict,
    db_session: Session,
    parser,
    *,
    ingest_fn: Callable = ingest_doc,
    settings_obj: Settings = settings,
    doc_model=Doc,
):
    """Process a single CouchDB change entry"""
    doc = change.get("doc")
    if not doc:
        logger.debug(f"No doc in change {change.get('id')}")
        return

    doc_id = doc.get("_id")
    if doc.get("deleted", False):
        # Delete from Postgres
        deleted_count = (
            db_session.query(doc_model)
            .filter(doc_model.document_id == doc_id)
            .delete()
        )
        db_session.commit()
        logger.info(f"Deleted {deleted_count} chunks for doc {doc_id}")
        return

    if doc.get("type") != "plain":
        logger.debug(f"Skipping non-plain doc {doc['_id']}")
        return

    path = doc.get("path", "")
    if not (
        path.startswith(settings_obj.BLOG_PREFIX)
        or path.startswith(settings_obj.KB_PREFIX)
    ):
        logger.debug(f"Skipping doc outside blog/kb paths {doc['_id']}")
        return

    try:
        ingest_fn(db_session, doc, parser=parser)
    except Exception as e:
        logger.error(f"Failed to ingest doc {doc['_id']}: {e}")


def start_listener():
    """Start listener in a daemon thread"""
    thread = threading.Thread(
        target=listen_changes, daemon=True, name="CouchDBListener"
    )
    thread.start()
    logger.info("CouchDB listener started in background thread")
    return thread


def stop_listener():
    """Signal listener to stop"""
    STOP_LISTENER_EVENT.set()
    logger.info("CouchDB listener stopping...")
