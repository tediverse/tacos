import os

from dotenv import load_dotenv

# Load from .env file
load_dotenv()


class Config:
    # CouchDB
    COUCHDB_HOST = os.getenv("COUCHDB_HOST", "localhost")
    COUCHDB_PORT = int(os.getenv("COUCHDB_PORT", "5984"))
    COUCHDB_USERNAME = os.getenv("COUCHDB_USERNAME", "admin")
    COUCHDB_PASSWORD = os.getenv("COUCHDB_PASSWORD", "")
    COUCHDB_DATABASE = os.getenv("COUCHDB_DATABASE", "obsidian_db")

    # Postgres
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "postgres_db")

    # Blog
    BLOG_PREFIX = os.getenv("BLOG_PREFIX", "blog/")
    BLOG_API_URL: str = os.getenv("BLOG_API_URL", "http://localhost:8000")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @property
    def couchdb_url(self) -> str:
        return f"http://{self.COUCHDB_USERNAME}:{self.COUCHDB_PASSWORD}@{self.COUCHDB_HOST}:{self.COUCHDB_PORT}"

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USERNAME}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"


# Global config instance
config = Config()
