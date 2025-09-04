import pycouchdb

from app.config import config
from app.content_parser import ContentParser

# Initialize CouchDB connection
try:
    couch = pycouchdb.Server(config.couchdb_url)
    db = couch.database(config.COUCHDB_DATABASE)
    parser = ContentParser(db)
except Exception as e:
    raise e
