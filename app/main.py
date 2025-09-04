import base64
import logging
import re
import urllib.parse
from typing import List

import frontmatter
import pycouchdb
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

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


def get_image_from_couchdb(image_path: str):
    """
    Retrieve an image from CouchDB using the ContentParser
    """
    try:
        # Try to get the image metadata document
        # First try with the exact path
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

            # Try to manually reconstruct from children as a fallback
            image_data = manually_reconstruct_image(doc)
            if not image_data:
                return None, None

        # Try to determine content type from filename
        if image_path.lower().endswith(".jpg") or image_path.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        elif image_path.lower().endswith(".png"):
            content_type = "image/png"
        elif image_path.lower().endswith(".gif"):
            content_type = "image/gif"
        elif image_path.lower().endswith(".svg"):
            content_type = "image/svg+xml"
        else:
            content_type = "application/octet-stream"

        return image_data, content_type

    except pycouchdb.exceptions.NotFound:
        logger.warning(f"Image not found in CouchDB: {image_path}")
        return None, None
    except Exception as e:
        logger.error(f"Error retrieving image {image_path}: {e}")
        return None, None


def manually_reconstruct_image(doc: dict) -> bytes:
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


def process_image_references(content: str, base_url: str) -> str:
    """
    Process markdown content to update image references to use the FastAPI endpoint
    """
    # Replace Obsidian image references like ![[image.png]] with standard markdown
    obsidian_pattern = r"!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|svg|webp))\]\]"
    content = re.sub(obsidian_pattern, r"![](" + base_url + r"/\1)", content)

    # Replace absolute paths with our API endpoint
    # This pattern matches: ![alt text](/img/image.png)
    absolute_path_pattern = r"!\[\s*(.*?)\s*\]\(\s*/img/([^)]+)\s*\)"
    content = re.sub(absolute_path_pattern, r"![\1](" + base_url + r"/\2)", content)

    return content


@app.get("/images/{image_path:path}")
async def get_image(image_path: str):
    """
    Serve images directly from CouchDB with proper response handling
    """
    image_data, content_type = get_image_from_couchdb(f"img/{image_path}")

    if not image_data or not content_type:
        raise HTTPException(status_code=404, detail="Image not found")

    # Set proper content length header
    headers = {
        "Content-Length": str(len(image_data)),
        "Accept-Ranges": "bytes",
    }

    return Response(content=image_data, media_type=content_type, headers=headers)


def parse_post_data(doc: dict, slug: str, include_content: bool = False) -> dict:
    """Parse frontmatter and return standardized post data"""
    try:
        # Use the ContentParser to get markdown content
        markdown = parser.get_markdown_content(doc)
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


@app.get("/posts", response_model=List[PostSummary])
def list_posts():
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
