import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # CouchDB Configuration
    COUCHDB_HOST = os.getenv("COUCHDB_HOST", "localhost")
    COUCHDB_PORT = int(os.getenv("COUCHDB_PORT", "5984"))
    COUCHDB_USERNAME = os.getenv("COUCHDB_USERNAME", "admin")
    COUCHDB_PASSWORD = os.getenv("COUCHDB_PASSWORD", "")
    COUCHDB_DATABASE = os.getenv("COUCHDB_DATABASE", "obsidian_db")

    # Blog Configuration
    BLOG_PREFIX = os.getenv("BLOG_PREFIX", "blog/")
    BLOG_API_URL: str = os.getenv(
        "BLOG_API_URL", "http://localhost:8000"
    )

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @property
    def couchdb_url(self) -> str:
        """Construct CouchDB URL from components."""
        return f"http://{self.COUCHDB_USERNAME}:{self.COUCHDB_PASSWORD}@{self.COUCHDB_HOST}:{self.COUCHDB_PORT}"


# Global config instance
config = Config()
