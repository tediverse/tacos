import textwrap

import pytest

from app.schemas.blog import PostDetail, PostSummary
from app.services.posts_service import (
    PostsService,
    calculate_reading_time,
    parse_post_data,
)
from tests.conftest import FakeRepo


class FakeParser:
    def __init__(self, content_by_id: dict[str, str]):
        self.content_by_id = content_by_id

    def get_markdown_content(self, doc: dict) -> str | None:
        raw = self.content_by_id.get(doc.get("_id"))
        if raw is None:
            return None
        return textwrap.dedent(raw).lstrip()


class FakeViewService:
    def __init__(self, counts: dict[str, int]):
        self.counts = counts
        self.calls = []

    def get_views_for_slugs(self, slugs):
        slugs_list = list(slugs)
        self.calls.append(tuple(slugs_list))
        return {slug: self.counts.get(slug, 0) for slug in slugs_list}

    def get_view_count(self, slug: str) -> int:
        self.calls.append(slug)
        return self.counts.get(slug, 0)


def test_list_posts_sorts_by_published_desc():
    docs = [
        {
            "_id": "blog/2024/newer.md",
            "path": "blog/2024/newer.md",
            "type": "plain",
        },
        {
            "_id": "blog/2023/older.md",
            "path": "blog/2023/older.md",
            "type": "plain",
        },
        {
            "_id": "blog/empty.md",
            "path": "blog/empty.md",
            "type": "plain",
        },
    ]

    parser = FakeParser(
        {
            "blog/2024/newer.md": """
            ---
            title: Newer Post
            publishedAt: 2024-06-01
            image: /img/hero.png
            tags: [python, ai]
            ---
            The body of the newer post.
            """,
            "blog/2023/older.md": """
            ---
            title: Older Post
            publishedAt: 2023-12-31
            ---
            Older content.
            """,
        }
    )
    views = FakeViewService({})
    service = PostsService(
        FakeRepo(docs), parser, views, base_image_url="http://localhost:8000"
    )

    result = service.list_posts()

    assert [post.slug for post in result] == ["2024/newer", "2023/older"]
    assert result[0].readingTime == "1 min"
    assert isinstance(result[0], PostSummary)


def test_list_posts_enriches_with_views_and_image_base():
    docs = [
        {"_id": "blog/with-image.md", "path": "blog/with-image.md", "type": "plain"},
    ]

    parser = FakeParser(
        {
            "blog/with-image.md": """
            ---
            title: Hero
            publishedAt: 2024-06-01
            image: /img/hero.png
            ---
            content
            """,
        }
    )
    views = FakeViewService({"with-image": 7})
    service = PostsService(
        FakeRepo(docs), parser, views, base_image_url="http://localhost:8000"
    )

    result = service.list_posts()

    assert result[0].image == "http://localhost:8000/images/hero.png"
    assert result[0].views == 7
    assert views.calls[0] == ("with-image",)


def test_list_posts_orders_with_missing_dates_and_drafts():
    docs = [
        {"_id": "blog/no-date.md", "path": "blog/no-date.md", "type": "plain"},
        {"_id": "blog/with-date.md", "path": "blog/with-date.md", "type": "plain"},
        {"_id": "blog/draft.md", "path": "blog/draft.md", "type": "plain"},
    ]

    parser = FakeParser(
        {
            "blog/no-date.md": """
            ---
            title: No Date
            ---
            content
            """,
            "blog/with-date.md": """
            ---
            title: With Date
            publishedAt: 2023-01-01
            ---
            content
            """,
            "blog/draft.md": """
            ---
            title: Draft Post
            draft: true
            publishedAt: 2022-05-01
            ---
            draft content
            """,
        }
    )
    service = PostsService(
        FakeRepo(docs),
        parser,
        FakeViewService({}),
        base_image_url="http://localhost:8000",
    )

    result = service.list_posts()

    assert [p.slug for p in result] == ["with-date", "draft", "no-date"]
    assert result[1].draft is True  # drafts are included/preserved


def test_get_post_returns_detail_with_processed_content():
    doc = {
        "_id": "blog/2024/hello.md",
        "path": "blog/2024/hello.md",
        "type": "plain",
    }
    markdown = """
    ---
    title: Hello Title
    publishedAt: 2024-08-01
    coAuthors: [Ada, Bob]
    draft: true
    ---
    Raw content here
    """

    parser = FakeParser({doc["_id"]: markdown})
    views = FakeViewService({"2024/hello": 42})
    service = PostsService(
        FakeRepo([doc]),
        parser,
        views,
        process_image_refs=lambda content, base_url: f"processed:{content}",
    )

    result = service.get_post("2024/hello")

    assert isinstance(result, PostDetail)
    assert result.slug == "2024/hello"
    assert result.title == "Hello Title"
    assert result.content.startswith("processed:")
    assert result.views == 42
    assert result.publishedAt == "2024-08-01"
    assert result.coAuthors == ["Ada", "Bob"]
    assert result.draft is True


def test_get_post_returns_none_when_not_found():
    service = PostsService(
        repo=FakeRepo([]),
        parser=FakeParser({}),
        view_service=FakeViewService({}),
    )

    assert service.get_post("missing") is None


def test_parse_post_data_returns_none_when_missing_markdown():
    doc = {"_id": "blog/empty.md", "path": "blog/empty.md", "type": "plain"}
    result = parse_post_data(doc, "blog/empty", parser=FakeParser({}))

    assert result is None


@pytest.mark.parametrize(
    ("coauthors_yaml", "expected"),
    [
        ("coAuthors: Solo", ["Solo"]),
        ("coAuthors: [Ada, Bob]", ["Ada", "Bob"]),
        ("coAuthors: [null, Eve]", ["Eve"]),  # drops nulls
        ("", []),  # missing field
    ],
)
def test_parse_post_data_normalizes_coauthors(coauthors_yaml, expected):
    doc = {"_id": "blog/coauth.md", "path": "blog/coauth.md", "type": "plain"}
    markdown = f"""
    ---
    title: Example
    {coauthors_yaml}
    summary: Quick summary
    tags: [t1, t2]
    updatedAt: 2024-01-02
    ---
    body text
    """
    parser = FakeParser({doc["_id"]: markdown})

    result = parse_post_data(doc, "coauth", parser=parser)

    assert result["coAuthors"] == expected
    assert result["summary"] == "Quick summary"
    assert result["tags"] == ["t1", "t2"]
    assert result["updatedAt"] == "2024-01-02"


def test_parse_post_data_converts_datetime_dates():
    doc = {"_id": "blog/dates.md", "path": "blog/dates.md", "type": "plain"}
    markdown = """
    ---
    title: Dates
    publishedAt: 2023-05-01
    updatedAt: 2024-01-02T03:04:05
    ---
    body
    """
    parser = FakeParser({doc["_id"]: markdown})

    result = parse_post_data(doc, "dates", parser=parser)

    assert result["publishedAt"] == "2023-05-01"
    assert result["updatedAt"].startswith("2024-01-02")


def test_parse_post_data_returns_none_on_exception():
    doc = {"_id": "blog/bad.md", "path": "blog/bad.md", "type": "plain"}

    class BoomParser(FakeParser):
        def get_markdown_content(self, doc):  # type: ignore
            raise RuntimeError("boom")

    parser = BoomParser({})
    result = parse_post_data(doc, "bad", parser=parser)

    assert result is None


@pytest.mark.parametrize(
    ("word_count", "expected"),
    [
        (0, "1 min"),
        (1, "1 min"),
        (200, "1 min"),
        (201, "2 min"),
        (399, "2 min"),
        (400, "2 min"),
        (401, "3 min"),
    ],
)
def test_calculate_reading_time_rounds_up(word_count, expected):
    text = "word " * word_count
    assert calculate_reading_time(text.strip()) == expected
