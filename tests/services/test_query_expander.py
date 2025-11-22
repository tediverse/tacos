import pytest

from app.services.query_expander import QueryExpander


def test_expand_query_returns_same_for_empty():
    expander = QueryExpander(expansion_rules={})
    assert expander.expand_query("") == ""
    assert expander.expand_query("   ") == "   "


def test_expand_query_applies_rules_and_dedupes():
    rules = {"work": ["job", "work"], "job": ["job", "task"]}
    expander = QueryExpander(expansion_rules=rules)

    result = expander.expand_query("work history")

    # Should include original tokens plus non-duplicate synonyms in order
    assert result == "work history job"


def test_expand_query_uses_word_boundaries():
    rules = {"go": ["navigate", "open"]}
    expander = QueryExpander(expansion_rules=rules)

    # "gopher" should not trigger rule
    assert expander.expand_query("gopher article") == "gopher article"

    # "go" should trigger rule
    assert expander.expand_query("go home") == "go home navigate open"


def test_expand_query_case_insensitive():
    rules = {"GitHub": ["codehost"]}
    expander = QueryExpander(expansion_rules=rules)

    assert expander.expand_query("Tell me about github") == "Tell me about github codehost"


def test_expand_query_preserves_order_of_first_occurrence():
    rules = {"python": ["python", "py", "python3"], "py": ["py", "python"]}
    expander = QueryExpander(expansion_rules=rules)

    result = expander.expand_query("python tips")

    # Unique order: original words first, then new synonyms as first seen
    assert result == "python tips py python3"
