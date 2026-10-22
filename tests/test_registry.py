import pytest
from pathlib import Path
from datetime import date

import registry


def test_parse_frontmatter_valid():
    text = "---\nname: foo\ndescription: Bar\n---\n\n# Foo\n"
    data, body = registry.parse_frontmatter(text)
    assert data == {"name": "foo", "description": "Bar"}
    assert body == "\n# Foo\n"


def test_parse_frontmatter_closing_marker_at_eof():
    data, body = registry.parse_frontmatter("---\nname: foo\n---")
    assert data == {"name": "foo"}
    assert body == ""


def test_parse_frontmatter_missing():
    with pytest.raises(registry.FrontmatterError, match="missing frontmatter"):
        registry.parse_frontmatter("# No frontmatter\n")


def test_parse_frontmatter_unterminated():
    with pytest.raises(registry.FrontmatterError, match="unterminated"):
        registry.parse_frontmatter("---\nname: foo\n")


def test_parse_frontmatter_invalid_yaml():
    with pytest.raises(registry.FrontmatterError, match="invalid yaml"):
        registry.parse_frontmatter("---\nname: [\n---\n")


def test_parse_frontmatter_not_mapping():
    with pytest.raises(registry.FrontmatterError, match="not a mapping"):
        registry.parse_frontmatter("---\n- a\n---\n")


VALID = "name: foo\ndescription: Does foo.\n"


def make_skill(root: Path, name: str, frontmatter: str = VALID, body: str = "# Foo\n") -> Path:
    if frontmatter == VALID:
        frontmatter = frontmatter.replace("foo", name)
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return skill_dir


def test_load_skill(tmp_path):
    skill_dir = make_skill(tmp_path, "foo")
    skill = registry.load_skill(skill_dir)
    assert skill == registry.Skill("foo", {"name": "foo", "description": "Does foo."})


def test_load_skill_missing_file(tmp_path):
    skill_dir = tmp_path / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    with pytest.raises(registry.FrontmatterError, match="SKILL.md not found"):
        registry.load_skill(skill_dir)


def test_discover_sorted_and_skips_underscore(tmp_path):
    make_skill(tmp_path, "zeta")
    make_skill(tmp_path, "alpha")
    make_skill(tmp_path, "_template")
    assert [p.name for p in registry.discover(tmp_path)] == ["alpha", "zeta"]


def test_discover_no_skills_dir(tmp_path):
    assert registry.discover(tmp_path) == []


def test_validate_valid():
    assert registry.validate_skill(registry.Skill("foo", {"name": "foo", "description": "x"})) == []


def test_validate_full_optional_fields():
    data = {
        "name": "foo",
        "description": "x",
        "license": "MIT",
        "source": "https://example.com",
        "tags": ["a", "b-c"],
        "metadata": {"author": "me"},
        "unknown": 1,
    }
    assert registry.validate_skill(registry.Skill("foo", data)) == []


@pytest.mark.parametrize(
    "dirname, data, message",
    [
        ("foo", {"description": "x"}, "name is required"),
        ("foo", {"name": "", "description": "x"}, "name is required"),
        ("Foo", {"name": "Foo", "description": "x"}, "not kebab-case"),
        ("foo", {"name": "bar", "description": "x"}, "does not match folder"),
        ("a" * 65, {"name": "a" * 65, "description": "x"}, "longer than 64"),
        ("foo", {"name": "foo"}, "description is required"),
        ("foo", {"name": "foo", "description": "  "}, "description is required"),
        ("foo", {"name": "foo", "description": "x" * 1025}, "longer than 1024"),
        ("foo", {"name": "foo", "description": "x", "license": ""}, "license must be"),
        ("foo", {"name": "foo", "description": "x", "source": "http://x"}, "source must be"),
        ("foo", {"name": "foo", "description": "x", "tags": "a"}, "tags must be"),
        ("foo", {"name": "foo", "description": "x", "tags": ["Bad Tag"]}, "tags must be"),
        ("foo", {"name": "foo", "description": "x", "metadata": []}, "metadata must be"),
    ],
)
def test_validate_problems(dirname, data, message):
    problems = registry.validate_skill(registry.Skill(dirname, data))
    assert any(message in p for p in problems), problems


def test_load_all_prefixes_problems(tmp_path):
    make_skill(tmp_path, "good")
    make_skill(tmp_path, "bad", "name: other\ndescription: x\n")
    (tmp_path / "skills" / "empty").mkdir()
    skills, problems = registry.load_all(tmp_path)
    assert [s.dirname for s in skills] == ["bad", "good"]
    assert problems == [
        "skills/bad/SKILL.md: name 'other' does not match folder 'bad'",
        "skills/empty/SKILL.md: SKILL.md not found",
    ]


def test_build_index_sorts_and_omits_optional():
    skills = [
        registry.Skill("zeta", {"name": "zeta", "description": " Z \n"}),
        registry.Skill(
            "alpha",
            {
                "name": "alpha",
                "description": "A",
                "license": "MIT",
                "source": "https://x",
                "tags": ["t"],
                "metadata": {"v": "1"},
                "ignored": True,
            },
        ),
    ]
    index = registry.build_index(skills, date(2026, 10, 22))
    assert index == {
        "generated": "2026-10-22",
        "skills": [
            {
                "name": "alpha",
                "description": "A",
                "path": "skills/alpha",
                "license": "MIT",
                "source": "https://x",
                "tags": ["t"],
                "metadata": {"v": "1"},
            },
            {"name": "zeta", "description": "Z", "path": "skills/zeta"},
        ],
    }


def test_render_table():
    entries = [
        {"name": "a", "description": "Has | pipe\nand newline", "path": "skills/a", "tags": ["x", "y"]},
        {"name": "b", "description": "Plain", "path": "skills/b"},
    ]
    assert registry.render_table(entries) == (
        "| Skill | Description | Tags |\n"
        "|---|---|---|\n"
        "| [a](skills/a/) | Has \\| pipe and newline | x, y |\n"
        "| [b](skills/b/) | Plain |  |"
    )


def test_splice_readme_replaces_between_markers():
    text = "# T\n\nintro\n\n<!-- index:start -->\nold\n<!-- index:end -->\n\nfooter\n"
    out = registry.splice_readme(text, "TABLE")
    assert out == "# T\n\nintro\n\n<!-- index:start -->\nTABLE\n<!-- index:end -->\n\nfooter\n"


def test_splice_readme_missing_markers():
    with pytest.raises(ValueError, match="markers"):
        registry.splice_readme("# T\n", "TABLE")
