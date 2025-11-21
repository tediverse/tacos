import datetime
import logging
import math
import os
from typing import Iterable, List, Optional

import frontmatter

from app.config import config
from app.schemas.blog import PostDetail, PostSummary

logger = logging.getLogger(__name__)


class PostsService:
    def __init__(self, repo, parser, view_service):
        self.repo = repo
        self.parser = parser
        self.view_service = view_service

    def list_posts(self) -> List[PostSummary]:
        docs = self.repo.list_blog_docs()
        posts = []
        for doc in docs:
            slug = doc.get("path", "").removeprefix("blog/").removesuffix(".md")
            post_data = parse_post_data(
                doc, slug, include_content=False, parser=self.parser
            )
            if post_data:
                posts.append(post_data)

        posts.sort(key=lambda x: x.get("publishedAt") or "0000-01-01", reverse=True)
        view_counts = self.view_service.get_views_for_slugs(
            (p.get("slug") for p in posts)
        )
        return [
            PostSummary(**{**p, "views": view_counts.get(p["slug"], 0)}) for p in posts
        ]

    def get_post(self, slug: str) -> Optional[PostDetail]:
        doc = self.repo.get_blog_doc(slug)
        if not doc:
            return None
        post_data = parse_post_data(doc, slug, include_content=True, parser=self.parser)
        if not post_data:
            return None
        views = self.view_service.get_view_count(slug)
        return PostDetail(**{**post_data, "views": views})


def parse_post_data(
    doc: dict, slug: str, include_content: bool = False, *, parser
) -> Optional[dict]:
    """Parse frontmatter and return standardized post data"""
    try:
        markdown = parser.get_markdown_content(doc)
        if not markdown:
            logger.warning(f"No markdown content found for post {slug}")
            return None

        parsed = frontmatter.loads(markdown)
        metadata = parsed.metadata or {}

        reading_time = calculate_reading_time(parsed.content)

        image_field = metadata.get("image")
        processed_image = (
            _process_frontmatter_image(image_field, f"{config.BLOG_API_URL}/images")
            if image_field
            else None
        )

        slug = _normalize_slug(slug)
        title = _derive_title(metadata, slug)
        co_authors = _normalize_coauthors(
            (metadata or {}).get("coAuthors") or (metadata or {}).get("coauthors")
        )

        post_data = {
            "id": doc["_id"],
            "slug": slug,
            "title": title,
            "summary": metadata.get("summary"),
            "image": processed_image,
            "publishedAt": _convert_date(metadata.get("publishedAt")),
            "updatedAt": _convert_date(metadata.get("updatedAt")),
            "tags": metadata.get("tags", []),
            "readingTime": reading_time,
            "draft": metadata.get("draft", False),
            "coAuthors": co_authors,
        }

        if include_content:
            post_data["content"] = _process_image_refs(
                parsed.content, f"{config.BLOG_API_URL}/images"
            )

        return post_data
    except Exception as e:
        logger.warning(f"Failed to parse post {slug}: {e}")
        return None


def _process_image_refs(content: str, base_url: str) -> str:
    from app.services.image_service import process_image_references

    return process_image_references(content, base_url)


def _normalize_slug(slug: str) -> str:
    base, _ = os.path.splitext(slug)
    return base


def _derive_title(metadata: dict, slug: str) -> str:
    if metadata and metadata.get("title"):
        return metadata["title"]
    clean_slug = slug.split("/", 1)[-1]
    clean_slug = clean_slug.replace("-", " ").replace("_", " ")
    return clean_slug.title()


def _normalize_coauthors(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return [str(value)]


def _convert_date(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _process_frontmatter_image(image_path: str, base_url: str) -> str:
    if not image_path:
        return image_path
    if image_path.startswith("/img/"):
        filename = image_path[5:]
        return f"{base_url}/{filename}"
    return image_path


def calculate_reading_time(text: str) -> str:
    words = text.split()
    minutes = math.ceil(len(words) / 200) or 1
    return f"{minutes} min"
