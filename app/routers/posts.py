import logging
import urllib.parse
from typing import List

from fastapi import APIRouter, HTTPException

from app.config import config
from app.db.couchdb import db
from app.schemas.blog import PostDetail, PostSummary
from app.services.post_service import parse_post_data

logger = logging.getLogger(__name__)

router = APIRouter()


def _filter_blog_docs(docs):
    """Helper function to filter and return only blog documents."""
    blog_docs = []

    for doc in docs:
        # Skip deleted docs
        if doc.get("deleted", False):
            continue

        if doc.get("type") == "plain" and doc.get("path", "").startswith(
            config.BLOG_PREFIX
        ):
            blog_docs.append(doc)

    return blog_docs


@router.get("/posts", response_model=List[PostSummary])
def list_posts():
    """Get all posts metadata."""
    try:
        all_docs = [row.get("doc", row) for row in db.all(include_docs=True)]
        blog_docs = _filter_blog_docs(all_docs)
        posts: List[PostSummary] = []

        for doc in blog_docs:
            slug = (
                doc.get("path", "").removeprefix(config.BLOG_PREFIX).removesuffix(".md")
            )

            post_data = parse_post_data(doc, slug, include_content=False)
            if post_data:
                posts.append(PostSummary(**post_data))

        # Sort by publishedAt desc
        posts.sort(key=lambda x: x.publishedAt or "0000-01-01", reverse=True)
        return posts

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve posts")


@router.get("/posts/{slug}", response_model=PostDetail)
def get_post(slug: str):
    """Get a single post by slug."""
    # Construct the expected document ID
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"

    try:
        # URL-encode the document ID to handle special characters like '/' and '.'
        encoded_doc_id = urllib.parse.quote(doc_id, safe="")
        blog_doc = db.get(encoded_doc_id)

        # Verify it's a valid blog post
        path = blog_doc.get("path", blog_doc.get("_id", ""))
        if (
            blog_doc.get("type") == "plain"
            and path.startswith(config.BLOG_PREFIX)
            and not blog_doc.get("deleted", False)
        ):
            post_data = parse_post_data(blog_doc, slug, include_content=True)
            if not post_data:
                raise HTTPException(status_code=500, detail="Failed to parse post")

            return PostDetail(**post_data)
        else:
            raise HTTPException(status_code=404, detail="Post not found")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # If direct fetch fails, fall back to searching all documents
        logger.warning(f"Direct fetch failed for {doc_id}, falling back to search: {e}")
        all_docs = [row.get("doc", row) for row in db.all(include_docs=True)]
        blog_doc = next(
            (
                doc
                for doc in all_docs
                if doc.get("_id") == doc_id
                and doc.get("type") == "plain"
                and not doc.get("deleted", False)
            ),
            None,
        )

        if not blog_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        post_data = parse_post_data(blog_doc, slug, include_content=True)
        if not post_data:
            raise HTTPException(status_code=500, detail="Failed to parse post")

        return PostDetail(**post_data)
