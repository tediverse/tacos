from app.dependencies import get_post_view_service, get_posts_repo, get_posts_service
from app.repos.posts_repo import CouchPostsRepo
from app.services.post_view_service import PostViewService
from app.services.posts_service import PostsService


def test_get_post_view_service_constructs_service():
    class FakeDB:
        pass

    db = FakeDB()
    svc = get_post_view_service(db=db)

    assert isinstance(svc, PostViewService)
    assert svc.db is db


def test_get_posts_repo_constructs_repo():
    class FakeCouch:
        pass

    couch_db = FakeCouch()
    repo = get_posts_repo(couch=(couch_db, None))

    assert isinstance(repo, CouchPostsRepo)
    assert repo.db is couch_db


def test_get_posts_service_constructs_service():
    class FakeRepo:
        pass

    class FakeViewService:
        pass

    repo = FakeRepo()
    view_svc = FakeViewService()
    svc = get_posts_service(repo=repo, view_service=view_svc)

    assert isinstance(svc, PostsService)
    assert svc.repo is repo
    assert svc.view_service is view_svc
