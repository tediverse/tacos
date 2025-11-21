import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.db import couchdb
from app.services.image_service import get_image_from_couchdb

logger = logging.getLogger(__name__)

router = APIRouter()


def get_image_dependencies():
    return couchdb.db, couchdb.parser


@router.get("/images/{image_path:path}")
async def get_image(image_path: str, deps=Depends(get_image_dependencies)):
    """
    Serve images directly from CouchDB
    """
    db, parser = deps
    image_data, content_type = get_image_from_couchdb(
        f"img/{image_path}", db=db, parser=parser
    )

    if not image_data or not content_type:
        raise HTTPException(status_code=404, detail="Image not found")

    # Set proper content length header
    headers = {
        "Content-Length": str(len(image_data)),
        "Accept-Ranges": "bytes",
    }

    return Response(content=image_data, media_type=content_type, headers=headers)
