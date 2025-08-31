import logging
from typing import List

import frontmatter
import pycouchdb
from fastapi import FastAPI, HTTPException

from app.config import config
from app.content_parser import ContentParser
from app.models import PostDetail, PostSummary

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


@app.get("/posts", response_model=List[PostSummary])
def list_posts():
    try:
        all_docs = [row.get("doc", row) for row in db.all(include_docs=True)]
        posts = []

        for doc in all_docs:
            if doc.get("type") != "plain" or not doc.get("path", "").startswith(
                config.BLOG_PREFIX
            ):
                continue

            slug = (
                doc.get("path", "").removeprefix(config.BLOG_PREFIX).removesuffix(".md")
            )
            title = summary = published_at = None
            tags = []

            try:
                markdown = parser.get_content(doc, all_docs)
                if markdown:
                    metadata = frontmatter.loads(markdown).metadata
                    title = metadata.get("title")
                    summary = metadata.get("summary")
                    published_at = metadata.get("publishedAt")
                    tags = metadata.get("tags", [])
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter for {slug}: {e}")

            posts.append(
                PostSummary(
                    id=doc["_id"],
                    slug=slug,
                    title=title,
                    summary=summary,
                    publishedAt=published_at,
                    tags=tags,
                )
            )

        return posts
    except Exception as e:
        logger.error(f"Error listing posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve posts")


@app.get("/posts/{slug}", response_model=PostDetail)
def get_post(slug: str):
    """Get a single post by slug."""
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"

    try:
        # Fetch all docs and find the one matching the slug
        all_docs = list(db.all(include_docs=True))
        blog_doc = next(
            (
                row.get("doc", row)
                for row in all_docs
                if row.get("id") == doc_id or row.get("_id") == doc_id
            ),
            None,
        )

        if not blog_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Reconstruct content (handles linked attachments if any)
        markdown = parser.get_content(blog_doc, all_docs)
        parsed = frontmatter.loads(markdown)

        return PostDetail(
            id=doc_id,
            title=parsed.metadata.get("title"),
            summary=parsed.metadata.get("summary"),
            image=parsed.metadata.get("image"),
            publishedAt=parsed.metadata.get("publishedAt"),
            tags=parsed.metadata.get("tags", []),
            content=parsed.content,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting post {slug}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
