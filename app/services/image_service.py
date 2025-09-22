import logging
import re
import urllib.parse
from typing import Optional, Tuple

import pycouchdb

from app.db.couchdb import db, parser

logger = logging.getLogger(__name__)


def get_image_from_couchdb(image_path: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Retrieve an image from CouchDB using the ContentParser
    """
    try:
        # Try to get the image metadata document
        try:
            doc = db.get(image_path)
        except pycouchdb.exceptions.NotFound:
            # If not found, try URL-encoded version
            encoded_path = urllib.parse.quote(image_path, safe="")
            doc = db.get(encoded_path)

        # Use the ContentParser to get the binary image data
        image_data = parser.get_binary_content(doc)

        if not image_data:
            logger.warning(f"No image data found for: {image_path}")
            return None, None

        # Verify we have the complete image data
        expected_size = doc.get("size")
        if expected_size and len(image_data) != expected_size:
            logger.warning(
                f"Image size mismatch for {image_path}. Expected: {expected_size}, Got: {len(image_data)}"
            )
            return None, None

        # Determine content type from filename
        content_type = get_content_type_from_filename(image_path)

        return image_data, content_type

    except pycouchdb.exceptions.NotFound:
        logger.warning(f"Image not found in CouchDB: {image_path}")
        return None, None
    except Exception as e:
        logger.error(f"Error retrieving image {image_path}: {e}")
        return None, None


def get_content_type_from_filename(filename: str) -> str:
    """
    Determine content type from file extension
    """
    filename = filename.lower()
    if filename.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif filename.endswith(".png"):
        return "image/png"
    elif filename.endswith(".gif"):
        return "image/gif"
    elif filename.endswith(".svg"):
        return "image/svg+xml"
    elif filename.endswith(".webp"):
        return "image/webp"
    else:
        return "application/octet-stream"


def process_image_references(content: str, base_url: str) -> str:
    """
    Process markdown content to update image references to use the FastAPI endpoint
    """
    # Pre-compile regex patterns for better performance
    obsidian_pattern = re.compile(r"!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|svg|webp))\]\]")
    absolute_path_pattern = re.compile(r"!\[\s*(.*?)\s*\]\(\s*/img/([^)]+)\s*\)")

    # Replace Obsidian image references
    content = obsidian_pattern.sub(r"![](" + base_url + r"/\1)", content)

    # Replace absolute paths
    content = absolute_path_pattern.sub(r"![\1](" + base_url + r"/\2)", content)

    return content
