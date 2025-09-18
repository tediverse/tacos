import pycouchdb

from app.config import config
from app.services.content_parser import ContentParser

couch = pycouchdb.Server(config.couchdb_url)
db = couch.database(config.COUCHDB_DATABASE)
parser = ContentParser(db)
