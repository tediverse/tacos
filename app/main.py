import logging

from fastapi import FastAPI

from app.config import config
from app.routers import images, posts

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="tedawf_blog API", description="Simple FastAPI serving Obsidian blog posts"
)

app.include_router(images.router)
app.include_router(posts.router)


@app.get("/")
async def root():
    return {"message": "tedawf_blog API is running"}
