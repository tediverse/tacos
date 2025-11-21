import pycouchdb

from app.config import config
from app.services.content_parser import ContentParser


def get_couch():
    """
    Create a CouchDB database handle and matching ContentParser.
    Called at runtime to avoid import-time connections.
    """
    couch = pycouchdb.Server(config.couchdb_url)
    database = couch.database(config.COUCHDB_DATABASE)
    parser = ContentParser(database)
    return database, parser
