import logging
import time
import urllib.parse
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import config
from app.db.couchdb import get_couch
from app.db.postgres.base import get_db
from app.schemas.blog import PostDetail, PostSummary
from app.services.post_service import parse_post_data
from app.services.post_view_service import PostViewService

logger = logging.getLogger(__name__)

router = APIRouter()
VIEW_GUARD_TTL_SECONDS = 30
_recent_view_hits: Dict[str, float] = {}


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
def list_posts(db_session: Session = Depends(get_db), couch=Depends(get_couch)):
    """Get all posts metadata."""
    try:
        couch_db, parser = couch
        all_docs = [row.get("doc", row) for row in couch_db.all(include_docs=True)]
        blog_docs = _filter_blog_docs(all_docs)
        posts: List[dict] = []

        for doc in blog_docs:
            slug = (
                doc.get("path", "").removeprefix(config.BLOG_PREFIX).removesuffix(".md")
            )

            post_data = parse_post_data(doc, slug, include_content=False, parser=parser)
            if post_data:
                posts.append(post_data)

        # Sort by publishedAt desc
        posts.sort(key=lambda x: x.get("publishedAt") or "0000-01-01", reverse=True)

        view_service = PostViewService(db_session)
        view_counts = view_service.get_views_for_slugs(
            post.get("slug") for post in posts
        )
        enriched_posts = []
        for post in posts:
            post["views"] = view_counts.get(post["slug"], 0)
            enriched_posts.append(PostSummary(**post))

        return enriched_posts

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve posts")


@router.get("/posts/{slug}", response_model=PostDetail)
def get_post(
    slug: str, db_session: Session = Depends(get_db), couch=Depends(get_couch)
):
    """Get a single post by slug."""
    try:
        couch_db, parser = couch
        blog_doc = _get_blog_doc_by_slug(slug, couch_db)
        if not blog_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        post_data = parse_post_data(blog_doc, slug, include_content=True, parser=parser)
        if not post_data:
            raise HTTPException(status_code=500, detail="Failed to parse post")

        view_service = PostViewService(db_session)
        post_data["views"] = view_service.get_view_count(slug)
        return PostDetail(**post_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving post {slug}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve post")


@router.post("/views/{slug}")
def increment_post_views(
    slug: str,
    request: Request,
    db_session: Session = Depends(get_db),
    couch=Depends(get_couch),
):
    couch_db, _parser = couch
    blog_doc = _get_blog_doc_by_slug(slug, couch_db)
    if not blog_doc:
        raise HTTPException(status_code=404, detail="Post not found")

    client_ip = request.client.host if request.client else ""
    view_service = PostViewService(db_session)

    if client_ip and _should_skip_increment(client_ip, slug):
        views = view_service.get_view_count(slug)
        return {"views": views}

    try:
        views = view_service.increment_view(slug)
        return {"views": views}
    except Exception as e:
        logger.error(f"Failed to record view for {slug}: {e}")
        raise HTTPException(status_code=500, detail="Failed to record view")


def _get_blog_doc_by_slug(slug: str, couch_db) -> Optional[dict]:
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"

    try:
        encoded_doc_id = urllib.parse.quote(doc_id, safe="")
        blog_doc = couch_db.get(encoded_doc_id)
        if _is_valid_blog_doc(blog_doc):
            return blog_doc
    except Exception as e:
        logger.warning(f"Direct fetch failed for {doc_id}: {e}")

    all_docs = [row.get("doc", row) for row in couch_db.all(include_docs=True)]
    return next(
        (
            doc
            for doc in all_docs
            if doc.get("_id") == doc_id and _is_valid_blog_doc(doc)
        ),
        None,
    )


def _is_valid_blog_doc(doc: dict) -> bool:
    if not doc:
        return False
    path = doc.get("path", doc.get("_id", ""))
    return (
        doc.get("type") == "plain"
        and path.startswith(config.BLOG_PREFIX)
        and not doc.get("deleted", False)
    )


def _should_skip_increment(client_ip: str, slug: str) -> bool:
    now = time.monotonic()
    key = f"{client_ip}:{slug}"
    last_seen = _recent_view_hits.get(key)

    if last_seen and now - last_seen < VIEW_GUARD_TTL_SECONDS:
        return True

    _recent_view_hits[key] = now
    if len(_recent_view_hits) > 512:
        _prune_view_cache(now)
    return False


def _prune_view_cache(now: float) -> None:
    stale_keys = [
        key
        for key, ts in _recent_view_hits.items()
        if now - ts >= VIEW_GUARD_TTL_SECONDS
    ]
    for key in stale_keys:
        _recent_view_hits.pop(key, None)
