import datetime
import logging
from typing import Dict, Optional

import frontmatter

from app.config import config
from app.db.couchdb import parser
from app.services.image_service import process_image_references
from app.utils import calculate_reading_time

logger = logging.getLogger(__name__)


def parse_post_data(
    doc: dict, slug: str, include_content: bool = False
) -> Optional[Dict]:
    """Parse frontmatter and return standardized post data"""
    try:
        # Use the ContentParser to get markdown content
        markdown = parser.get_markdown_content(doc)
        parsed = frontmatter.loads(markdown)
        metadata = parsed.metadata

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

        post_data = {
            "id": doc["_id"],
            "slug": slug,
            "title": metadata.get("title", slug.replace("-", " ").title()),
            "summary": metadata.get("summary"),
            "image": processed_image,
            "publishedAt": convert_date_to_string(metadata.get("publishedAt")),
            "updatedAt": convert_date_to_string(metadata.get("updatedAt")),
            "tags": metadata.get("tags", []),
            "readingTime": reading_time,
            "draft": metadata.get("draft", False),
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
