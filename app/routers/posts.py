import logging
from typing import List

from fastapi import APIRouter, HTTPException

from app.config import config
from app.dependencies import db
from app.models import PostDetail, PostSummary
from app.services.post_service import parse_post_data

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/posts", response_model=List[PostSummary])
def list_posts():
    """Get all posts metadata."""
    try:
        all_docs = [row.get("doc", row) for row in db.all(include_docs=True)]
        posts: List[PostSummary] = []

        for doc in all_docs:
            # Skip deleted docs
            if doc.get("deleted", False):
                continue

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


@router.get("/posts/{slug}", response_model=PostDetail)
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
