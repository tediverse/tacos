from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import doc
from app.db.postgres import get_db
from app.schemas.doc import DocSchema

router = APIRouter()


@router.get("/mydocs", response_model=List[DocSchema])
def list_docs(db: Session = Depends(get_db)):
    return db.query(doc.Doc).all()
