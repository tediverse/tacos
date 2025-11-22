import datetime

import pytest

from app.schemas.blog import PostDetail, PostSummary
from app.services.posts_service import (
    PostsService,
    _convert_date,
    _derive_title,
    _normalize_coauthors,
    _normalize_slug,
    _process_frontmatter_image,
    _process_image_refs,
    calculate_reading_time,
    parse_post_data,
)
from app.settings import settings
from tests.conftest import FakeParser, FakeRepo, FakeViewService


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
        repo=FakeRepo(docs),
        view_service=views,
        parser=parser,
        base_image_url="http://localhost:8000",
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
        repo=FakeRepo(docs),
        parser=parser,
        view_service=views,
        base_image_url="http://localhost:8000",
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
        repo=FakeRepo(docs),
        parser=parser,
        view_service=FakeViewService({}),
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
        repo=FakeRepo([doc]),
        parser=parser,
        view_service=views,
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


def test_get_post_returns_none_when_parse_fails():
    doc = {"_id": "blog/bad.md", "path": "blog/bad.md", "type": "plain"}
    # parser will return None -> parse_post_data returns None
    service = PostsService(
        repo=FakeRepo([doc]),
        parser=FakeParser({}),  # no markdown content
        view_service=FakeViewService({}),
    )

    assert service.get_post("bad") is None


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


def test_parse_post_data_uses_default_base_image_url_when_not_provided():
    doc = {"_id": "blog/base.md", "path": "blog/base.md", "type": "plain"}
    markdown = """
    ---
    title: Base URL
    image: /img/base.jpg
    ---
    Body
    """
    parser = FakeParser({doc["_id"]: markdown})

    result = parse_post_data(doc, "base", include_content=False, parser=parser)

    assert result["image"] == f"{settings.BLOG_API_URL}/images/base.jpg"


def test_parse_post_data_processes_content_with_default_image_refs():
    doc = {"_id": "blog/with-images.md", "path": "blog/with-images.md", "type": "plain"}
    markdown = """
    ---
    title: Images
    publishedAt: 2024-09-01
    image: /img/cover.jpg
    ---
    Body with ![[pic.png]] and ![alt](/img/photo.jpg)
    """
    parser = FakeParser({doc["_id"]: markdown})

    result = parse_post_data(
        doc,
        "with-images",
        include_content=True,
        parser=parser,
        process_image_refs=None,
        base_image_url="http://localhost:9000",
    )

    assert result["image"] == "http://localhost:9000/images/cover.jpg"
    expected = "Body with ![](http://localhost:9000/images/pic.png) and ![alt](http://localhost:9000/images/photo.jpg)"
    assert result["content"].strip() == expected


def test_process_image_refs_wrapper_uses_image_service():
    content = "![[a.png]] and ![alt](/img/b.jpg)"
    out = _process_image_refs(content, "http://base/images")
    assert out == "![](http://base/images/a.png) and ![alt](http://base/images/b.jpg)"


def test_process_frontmatter_image_variants():
    base = "http://host/images"
    assert (
        _process_frontmatter_image("/img/hero.png", base)
        == "http://host/images/hero.png"
    )
    assert (
        _process_frontmatter_image("https://cdn/foo.jpg", base) == "https://cdn/foo.jpg"
    )
    assert _process_frontmatter_image(None, base) is None


def test_normalize_slug_and_title_helpers():
    assert _normalize_slug("2024/post.md") == "2024/post"
    assert _derive_title({}, "2024/hello-world") == "Hello World"
    assert _derive_title({"title": "Custom"}, "ignored") == "Custom"
    assert _normalize_coauthors({"solo"}) == ["solo"]
    assert _normalize_coauthors(123) == ["123"]


def test_convert_date_handles_datetime_and_passthrough():
    d = datetime.date(2023, 5, 1)
    dt = datetime.datetime(2024, 1, 2, 3, 4, 5)
    assert _convert_date(d) == "2023-05-01"
    assert _convert_date(dt).startswith("2024-01-02T03:04:05")
    assert _convert_date("2020-01-01") == "2020-01-01"


def test_posts_service_builds_default_parser_when_repo_has_db():
    class RepoWithDb(FakeRepo):
        def __init__(self):
            super().__init__([])
            self.db = "db-marker"

    service = PostsService(repo=RepoWithDb(), view_service=FakeViewService({}))

    from app.services.content_parser import ContentParser

    assert isinstance(service.parser, ContentParser)


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
