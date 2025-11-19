from typing import Dict, Iterable, List

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.post_view import PostView


class PostViewService:
    def __init__(self, db: Session):
        self.db = db

    def get_views_for_slugs(self, slugs: Iterable[str]) -> Dict[str, int]:
        normalized: List[str] = list({slug for slug in slugs if slug})
        if not normalized:
            return {}

        rows = (
            self.db.query(PostView.slug, PostView.view_count)
            .filter(PostView.slug.in_(normalized))
            .all()
        )
        return {slug: count for slug, count in rows}

    def get_view_count(self, slug: str) -> int:
        record = self.db.get(PostView, slug)
        return record.view_count if record else 0

    def increment_view(self, slug: str) -> int:
        stmt = (
            insert(PostView)
            .values(slug=slug, view_count=1)
            .on_conflict_do_update(
                index_elements=[PostView.slug],
                set_={
                    "view_count": PostView.view_count + 1,
                    "updated_at": func.now(),
                },
            )
            .returning(PostView.view_count)
        )

        result = self.db.execute(stmt)
        self.db.commit()
        return result.scalar_one()
