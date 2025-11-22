from app.config import config
from app.repos.posts_repo import CouchPostsRepo
from tests.conftest import FakeCouchDB


def test_list_blog_docs_filters_plain_prefix_and_deleted():
    docs = {
        "ok": {"_id": "blog/post.md", "path": "blog/post.md", "type": "plain"},
        "other_prefix": {
            "_id": "notes/file.md",
            "path": "notes/file.md",
            "type": "plain",
        },
        "not_plain": {"_id": "blog/bad.md", "path": "blog/bad.md", "type": "leaf"},
        "deleted": {
            "_id": "blog/old.md",
            "path": "blog/old.md",
            "type": "plain",
            "deleted": True,
        },
    }
    repo = CouchPostsRepo(FakeCouchDB(docs))

    result = repo.list_blog_docs()

    assert result == [docs["ok"]]


def test_get_blog_doc_returns_direct_hit_with_encoded_slash():
    slug = "2024/hello"
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"  # blog/2024/hello.md
    encoded = doc_id.replace("/", "%2F")
    doc = {"_id": doc_id, "path": doc_id, "type": "plain"}
    # FakeCouchDB will raise NotFound when the requested key is missing
    repo = CouchPostsRepo(FakeCouchDB({encoded: doc, doc_id: doc}, track_calls=True))

    found = repo.get_blog_doc(slug)

    assert found == doc
    assert repo.db.calls[0] == encoded  # first tried encoded id


def test_get_blog_doc_skips_invalid_direct_doc_and_falls_back():
    slug = "2024/hello"
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"
    encoded = doc_id.replace("/", "%2F")
    invalid = {"_id": encoded, "path": encoded, "type": "leaf"}  # not valid
    valid = {"_id": doc_id, "path": doc_id, "type": "plain"}
    repo = CouchPostsRepo(
        FakeCouchDB({encoded: invalid, doc_id: valid}, track_calls=True)
    )

    found = repo.get_blog_doc(slug)

    assert found == valid
    # encoded was attempted, then fell back to list
    assert any(call.startswith("all(") for call in repo.db.calls)


def test_get_blog_doc_falls_back_to_list_when_direct_missing():
    slug = "2023/missing-direct"
    doc_id = f"{config.BLOG_PREFIX}{slug}.md"
    doc = {"_id": doc_id, "path": doc_id, "type": "plain"}
    # Only unencoded id present to force fallback path
    repo = CouchPostsRepo(FakeCouchDB({doc_id: doc}, track_calls=True))

    found = repo.get_blog_doc(slug)

    assert found == doc
    assert any(call.startswith("all(") for call in repo.db.calls)


def test_get_blog_doc_returns_none_when_not_found():
    repo = CouchPostsRepo(
        FakeCouchDB(
            {
                "a": {"_id": "blog/a.md", "path": "blog/a.md", "type": "plain"},
                "b": {"_id": "blog/b.md", "path": "blog/b.md", "type": "plain"},
            },
            track_calls=True,
        )
    )
    assert repo.get_blog_doc("nope") is None


def test_is_valid_checks_type_prefix_and_deleted():
    assert (
        CouchPostsRepo._is_valid({"type": "plain", "path": f"{config.BLOG_PREFIX}x"})
        is True
    )
    assert (
        CouchPostsRepo._is_valid({"type": "leaf", "path": f"{config.BLOG_PREFIX}x"})
        is False
    )
    assert CouchPostsRepo._is_valid({"type": "plain", "path": "other/x"}) is False
    assert (
        CouchPostsRepo._is_valid(
            {"type": "plain", "path": f"{config.BLOG_PREFIX}x", "deleted": True}
        )
        is False
    )
    assert CouchPostsRepo._is_valid(None) is False
