import pycouchdb

from app.services.content_parser import ContentParser
from app.settings import settings


def get_couch():
    """
    Create a CouchDB database handle and matching ContentParser.
    Called at runtime to avoid import-time connections.
    """
    couch = pycouchdb.Server(settings.couchdb_url)
    database = couch.database(settings.COUCHDB_DATABASE)
    parser = ContentParser(database)
    return database, parser
