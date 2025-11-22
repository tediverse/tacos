from fastapi import Depends

from app.db.couchdb import get_couch
from app.db.postgres.base import get_db
from app.repos.posts_repo import CouchPostsRepo
from app.services.post_view_service import PostViewService
from app.services.posts_service import PostsService


def get_post_view_service(db=Depends(get_db)):
    return PostViewService(db)


def get_posts_repo(couch=Depends(get_couch)):
    couch_db, _parser = couch
    return CouchPostsRepo(couch_db)


def get_posts_service(
    repo=Depends(get_posts_repo),
    view_service=Depends(get_post_view_service),
):
    return PostsService(repo=repo, view_service=view_service)
