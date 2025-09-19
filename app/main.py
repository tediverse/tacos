import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import config
from app.routers import images, posts, rag
from app.services.couchdb_listener import start_listener, stop_listener

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TACOS API", description="Ted's AI Chatbot & Obsidian Sync")


@asynccontextmanager
async def lifespan(app: FastAPI):
    listener_thread = start_listener()
    logger.info("CouchDB listener started in background thread")

    try:
        yield
    finally:
        stop_listener()
        listener_thread.join(timeout=10)
        logger.info("CouchDB listener exited gracefully")


app.router.lifespan_context = lifespan

app.include_router(images.router)
app.include_router(posts.router)
app.include_router(rag.router)


@app.get("/")
async def root():
    return {"message": "TACOS API is running"}
