import os

from dotenv import load_dotenv

# Load local env in dev, or .env in prod
if os.path.exists(".env.local"):
    load_dotenv(".env.local")
else:
    load_dotenv(".env")


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
    BASE_BLOG_URL: str = os.getenv("BASE_BLOG_URL", "http://localhost:3000")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Our own API Key
    TACOS_API_KEY: str = os.getenv("TACOS_API_KEY", "")

    # Knowledge Base
    KB_PREFIX = os.getenv("KNOWLEDGE_BASE_PREFIX", "kb/")

    # Portfolio
    PORTFOLIO_PREFIX = os.getenv("PORTFOLIO_PREFIX", "portfolio/")

    @property
    def couchdb_url(self) -> str:
        return f"http://{self.COUCHDB_USERNAME}:{self.COUCHDB_PASSWORD}@{self.COUCHDB_HOST}:{self.COUCHDB_PORT}"

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USERNAME}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"


# Global config instance
config = Config()
