import base64
import logging
import re
import urllib.parse
from typing import Optional, Tuple

import pycouchdb

from app.dependencies import db

logger = logging.getLogger(__name__)


def get_image_from_couchdb(image_path: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Retrieve an image from CouchDB
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
        from app.dependencies import parser

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

            # Try to manually reconstruct from children as a fallback
            image_data = manually_reconstruct_image(doc)
            if not image_data:
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


def manually_reconstruct_image(doc: dict) -> Optional[bytes]:
    """
    Manually reconstruct image from children chunks as a fallback
    """
    try:
        if "children" not in doc:
            return None

        children = doc["children"]
        image_chunks = []

        for child_id in children:
            try:
                child_doc = db.get(child_id)
                if "data" in child_doc:
                    # Decode base64 data
                    chunk_data = base64.b64decode(child_doc["data"])
                    image_chunks.append(chunk_data)
            except Exception as e:
                logger.error(f"Error retrieving child {child_id}: {e}")
                continue

        if image_chunks:
            # Combine all chunks
            image_data = b"".join(image_chunks)
            logger.info(
                f"Manually reconstructed image with {len(image_chunks)} chunks, total size: {len(image_data)}"
            )
            return image_data

    except Exception as e:
        logger.error(f"Error in manual image reconstruction: {e}")

    return None


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
