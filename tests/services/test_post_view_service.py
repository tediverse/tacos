from types import SimpleNamespace

from sqlalchemy.dialects.postgresql import insert

from app.models.post_view import PostView
from app.services.post_view_service import PostViewService
from tests.conftest import FakeSession


def test_get_views_for_slugs_returns_empty_on_none():
    service = PostViewService(FakeSession())
    assert service.get_views_for_slugs([]) == {}


def test_get_views_for_slugs_dedupes_and_returns_counts():
    rows = [("a", 2), ("b", 5)]
    session = FakeSession(rows=rows)
    service = PostViewService(session)

    result = service.get_views_for_slugs(["a", "b", "a"])

    assert result == {"a": 2, "b": 5}
    # filter called with IN over deduped slugs
    assert session.last_query.filtered is not None


def test_get_view_count_returns_zero_when_missing():
    service = PostViewService(FakeSession(record_map={}))
    assert service.get_view_count("missing") == 0


def test_get_view_count_returns_value():
    record = SimpleNamespace(view_count=7)
    service = PostViewService(FakeSession(record_map={"slug-1": record}))
    assert service.get_view_count("slug-1") == 7


def test_increment_view_executes_upsert_and_commits():
    session = FakeSession(execute_value=3)
    service = PostViewService(session)

    result = service.increment_view("post-xyz")

    assert result == 3
    assert session.executed_stmt is not None
    assert isinstance(session.executed_stmt, insert(PostView).__class__)
    assert session.committed is True
