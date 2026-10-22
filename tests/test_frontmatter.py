import pytest

from conftest import UPSTREAM_V1
from ferdigheter.frontmatter import dump_frontmatter, merge_frontmatter, parse_frontmatter
from ferdigheter.model import FrontmatterError


def test_parse_frontmatter_valid():
    text = "---\nname: foo\ndescription: Bar\n---\n\n# Foo\n"
    data, body = parse_frontmatter(text)
    assert data == {"name": "foo", "description": "Bar"}
    assert body == "\n# Foo\n"


def test_parse_frontmatter_closing_marker_at_eof():
    data, body = parse_frontmatter("---\nname: foo\n---")
    assert data == {"name": "foo"}
    assert body == ""


def test_parse_frontmatter_missing():
    with pytest.raises(FrontmatterError, match="missing frontmatter"):
        parse_frontmatter("# No frontmatter\n")


def test_parse_frontmatter_unterminated():
    with pytest.raises(FrontmatterError, match="unterminated"):
        parse_frontmatter("---\nname: foo\n")


def test_parse_frontmatter_invalid_yaml():
    with pytest.raises(FrontmatterError, match="invalid yaml"):
        parse_frontmatter("---\nname: [\n---\n")


def test_parse_frontmatter_not_mapping():
    with pytest.raises(FrontmatterError, match="not a mapping"):
        parse_frontmatter("---\n- a\n---\n")


def test_dump_frontmatter_round_trip():
    text = "---\nname: foo\ndescription: 'Quoted: yes'\ntags:\n- a\n---\n\n# Body\n"
    data, body = parse_frontmatter(text)
    assert parse_frontmatter(dump_frontmatter(data, body)) == (data, body)


def test_merge_frontmatter_appends_registry_fields_last():
    merged = merge_frontmatter(
        UPSTREAM_V1, {"license": "MIT", "source": "https://x", "tags": ["a"]}
    )
    data, body = parse_frontmatter(merged)
    assert list(data) == ["name", "description", "license", "source", "tags"]
    assert data["license"] == "MIT"
    assert body == "\n# Foo v1\n"


def test_merge_frontmatter_keeps_registry_name_in_place():
    merged = merge_frontmatter(
        UPSTREAM_V1, {"name": "vercel-foo", "license": "MIT", "source": "https://x", "tags": ["a"]}
    )
    data, body = parse_frontmatter(merged)
    assert list(data) == ["name", "description", "license", "source", "tags"]
    assert data["name"] == "vercel-foo"
    assert body == "\n# Foo v1\n"


def test_merge_frontmatter_strips_trailing_whitespace_in_strings():
    upstream = "---\nname: foo\ndescription: >\n  Folded text.\n\n\nlanguages:\n- a \n---\n\n# B\n"
    data, _ = parse_frontmatter(merge_frontmatter(upstream, {}))
    assert data["description"] == "Folded text."
    assert data["languages"] == ["a"]


def test_merge_frontmatter_without_overrides_drops_upstream_registry_fields():
    data, _ = parse_frontmatter(merge_frontmatter(UPSTREAM_V1, {}))
    assert "license" not in data
