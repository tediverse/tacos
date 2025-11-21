import datetime
import logging
import math
import os
from typing import Dict, List, Optional

import frontmatter

from app.config import config
from app.services.image_service import process_image_references

logger = logging.getLogger(__name__)


def parse_post_data(
    doc: dict, slug: str, include_content: bool = False, *, parser
) -> Optional[Dict]:
    """Parse frontmatter and return standardized post data"""
    try:
        # Use the ContentParser to get markdown content
        markdown = parser.get_markdown_content(doc)
        if not markdown:
            logger.warning(f"No markdown content found for post {slug}")
            return None

        parsed = frontmatter.loads(markdown)
        metadata = parsed.metadata or {}

        # Calculate reading time
        reading_time = calculate_reading_time(parsed.content)

        # Process the image url in frontmatter
        image_field = metadata.get("image")
        if image_field:
            processed_image = process_frontmatter_image(
                image_field, f"{config.BLOG_API_URL}/images"
            )
            logger.debug(
                f"Processed frontmatter image: {image_field} -> {processed_image}"
            )
        else:
            processed_image = None

        # Normalize slug (remove extension, humanize)
        slug = normalize_slug(slug)
        title = derive_title(metadata, slug)

        co_authors = normalize_coauthors(
            (metadata or {}).get("coAuthors") or (metadata or {}).get("coauthors")
        )

        post_data = {
            "id": doc["_id"],
            "slug": slug,
            "title": title,
            "summary": metadata.get("summary"),
            "image": processed_image,
            "publishedAt": convert_date_to_string(metadata.get("publishedAt")),
            "updatedAt": convert_date_to_string(metadata.get("updatedAt")),
            "tags": metadata.get("tags", []),
            "readingTime": reading_time,
            "draft": metadata.get("draft", False),
            "coAuthors": co_authors,
        }

        if include_content:
            # Process image references to point to our API
            logger.debug(f"Original content before processing: {parsed.content}")
            processed_content = process_image_references(
                parsed.content, f"{config.BLOG_API_URL}/images"
            )
            logger.debug(
                f"Processed content after image processing: {processed_content}"
            )
            post_data["content"] = processed_content

        return post_data

    except Exception as e:
        logger.warning(f"Failed to parse post {slug}: {e}")
        return None


def normalize_slug(slug: str) -> str:
    """Remove extension and normalize slug for display / navigation."""
    base, _ = os.path.splitext(slug)
    return base


def derive_title(metadata: dict, slug: str) -> str:
    """Get human-readable title for blog or KB note."""
    if metadata and metadata.get("title"):
        return metadata["title"]
    # For KB notes, convert filename to title
    clean_slug = slug.split("/", 1)[-1]  # Remove prefix (blog/ or kb/)
    clean_slug = clean_slug.replace("-", " ").replace("_", " ")
    return clean_slug.title()


def normalize_coauthors(value) -> List[str]:
    """
    Normalize co-author metadata into a list of strings for consistent API responses.
    """
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return [str(value)]


def convert_date_to_string(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def process_frontmatter_image(image_path: str, base_url: str) -> str:
    """
    Process a single image path from frontmatter to use the FastAPI endpoint
    """
    if not image_path:
        return image_path

    # Handle absolute paths like /img/abc.png
    if image_path.startswith("/img/"):
        # Remove /img/ prefix and prepend base_url
        filename = image_path[5:]  # Remove '/img/'
        return f"{base_url}/{filename}"

    return image_path


def calculate_reading_time(text: str) -> str:
    words = text.split()
    minutes = math.ceil(len(words) / 200) or 1
    return f"{minutes} min"
