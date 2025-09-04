import logging
from typing import List

import frontmatter
import pycouchdb
from fastapi import FastAPI, HTTPException

from app.config import config
from app.content_parser import ContentParser
from app.models import PostDetail, PostSummary
from app.utils import calculate_reading_time

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Blog API", description="Simple FastAPI server for Obsidian blog posts"
)

# Initialize CouchDB connection
try:
    couch = pycouchdb.Server(config.couchdb_url)
    db = couch.database(config.COUCHDB_DATABASE)
    parser = ContentParser(db)
    logger.info(f"Connected to CouchDB database: {config.COUCHDB_DATABASE}")
except Exception as e:
    logger.error(f"Failed to connect to CouchDB: {e}")
    raise


def parse_post_data(doc: dict, slug: str, include_content: bool = False) -> dict:
    """Parse frontmatter and return standardized post data"""
    try:
        markdown = parser.get_content(doc, [])
        parsed = frontmatter.loads(markdown)
        metadata = parsed.metadata

        # Calculate reading time
        reading_time = calculate_reading_time(parsed.content)

        post_data = {
            "id": doc["_id"],
            "slug": slug,
            "title": metadata.get("title", slug.replace("-", " ").title()),
            "summary": metadata.get("summary"),
            "image": metadata.get("image"),
            "publishedAt": metadata.get("publishedAt"),
            "updatedAt": metadata.get("updatedAt"),
            "tags": metadata.get("tags", []),
            "readingTime": reading_time,
            "draft": metadata.get("draft", False),
        }

        if include_content:
            post_data["content"] = parsed.content

        return post_data

    except Exception as e:
        logger.warning(f"Failed to parse post {slug}: {e}")
        return None


@app.get("/posts", response_model=List[PostSummary])
def list_posts():
    try:
        all_docs = [row.get("doc", row) for row in db.all(include_docs=True)]
        posts: List[PostSummary] = []

        for doc in all_docs:
            if doc.get("type") != "plain" or not doc.get("path", "").startswith(
                config.BLOG_PREFIX
            ):
                continue

            slug = (
                doc.get("path", "").removeprefix(config.BLOG_PREFIX).removesuffix(".md")
            )

            post_data = parse_post_data(doc, slug, include_content=False)
            if post_data:
                posts.append(PostSummary(**post_data))

        # Sort by publishedAt desc
        posts.sort(key=lambda x: x.publishedAt or "0000-01-01", reverse=True)
        return posts

    except Exception as e:
        logger.error(f"Error listing posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve posts")


@app.get("/posts/{slug}", response_model=PostDetail)
def get_post(slug: str):
    """Get a single post by slug."""
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"

    try:
        all_docs = [row.get("doc", row) for row in db.all(include_docs=True)]
        blog_doc = next((doc for doc in all_docs if doc.get("_id") == doc_id), None)

        if not blog_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        post_data = parse_post_data(blog_doc, slug, include_content=True)
        if not post_data:
            raise HTTPException(status_code=500, detail="Failed to parse post")

        return PostDetail(**post_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting post {slug}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
