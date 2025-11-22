from app.services.content_enhancer import ContentEnhancer


def test_enhance_content_includes_title_and_content():
    enhancer = ContentEnhancer()

    result = enhancer.enhance_content(
        title="My Title", content="Body text", metadata={"enrichment": []}
    )

    lines = result.splitlines()
    assert lines[0] == "Title: My Title"
    assert lines[-1] == "Content: Body text"


def test_enhance_content_handles_enrichment_list():
    enhancer = ContentEnhancer()
    result = enhancer.enhance_content(
        title="Doc", content="Body", metadata={"enrichment": ["first", "second"]}
    )

    assert "Additional Context:\nfirst\nsecond" in result


def test_enhance_content_adds_content_type():
    enhancer = ContentEnhancer()
    result = enhancer.enhance_content(
        title="Doc",
        content="Body",
        metadata={"enrichment": [], "contentType": "navigation"},
    )

    assert "Content Type: navigation" in result


def test_enhance_content_handles_missing_metadata():
    enhancer = ContentEnhancer()
    result = enhancer.enhance_content(title="", content="Only body", metadata=None)

    # No title line expected, but content is always included
    assert result.startswith("Content: Only body")
