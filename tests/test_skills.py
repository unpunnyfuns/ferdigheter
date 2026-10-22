from datetime import date

import pytest

from conftest import make_skill, write_manifest_file
from ferdigheter.model import FrontmatterError, Skill
from ferdigheter.skills import discover, load_all, load_skill, validate_skill


def test_load_skill(tmp_path):
    skill_dir = make_skill(tmp_path, "foo")
    skill = load_skill(skill_dir)
    assert skill == Skill("misc", "foo", {"name": "foo", "description": "Does foo."})


def test_load_skill_missing_file(tmp_path):
    skill_dir = tmp_path / "skills" / "misc" / "foo"
    skill_dir.mkdir(parents=True)
    with pytest.raises(FrontmatterError, match="SKILL.md not found"):
        load_skill(skill_dir)


def test_discover_sorted_and_skips_underscore(tmp_path):
    make_skill(tmp_path, "zeta", category="b")
    make_skill(tmp_path, "alpha", category="b")
    make_skill(tmp_path, "mid", category="a")
    make_skill(tmp_path, "_draft", category="a")
    (tmp_path / "skills" / "_template").mkdir()
    (tmp_path / "skills" / "_template" / "SKILL.md").write_text("---\nname: x\n---\n")
    (tmp_path / "skills" / "empty-category").mkdir()
    found = [(p.parent.name, p.name) for p in discover(tmp_path)]
    assert found == [("a", "mid"), ("b", "alpha"), ("b", "zeta")]


def test_discover_no_skills_dir(tmp_path):
    assert discover(tmp_path) == []


def test_validate_valid():
    assert validate_skill(Skill("misc", "foo", {"name": "foo", "description": "x"})) == []


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
    assert validate_skill(Skill("misc", "foo", data)) == []


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
        ("foo", {"name": "foo", "description": "x", "source": ""}, "source must be"),
        ("foo", {"name": "foo", "description": "x", "source": 3}, "source must be"),
        ("foo", {"name": "foo", "description": "x", "tags": "a"}, "tags must be"),
        ("foo", {"name": "foo", "description": "x", "tags": ["Bad Tag"]}, "tags must be"),
        ("foo", {"name": "foo", "description": "x", "metadata": []}, "metadata must be"),
        (
            "foo",
            {"name": "foo", "description": "x", "metadata": {"released": date(2026, 1, 1)}},
            "metadata must be JSON-serializable",
        ),
        (
            "foo",
            {"name": "foo", "description": "x <!-- index:end -->"},
            "description must not contain HTML comments",
        ),
    ],
)
def test_validate_problems(dirname, data, message):
    problems = validate_skill(Skill("misc", dirname, data))
    assert any(message in p for p in problems), problems


def test_load_all_prefixes_problems(tmp_path):
    make_skill(tmp_path, "good")
    make_skill(tmp_path, "bad", "name: other\ndescription: x\n")
    (tmp_path / "skills" / "misc" / "empty").mkdir()
    skills, problems = load_all(tmp_path)
    assert [s.dirname for s in skills] == ["bad", "good"]
    assert problems == [
        "skills/misc/bad/SKILL.md: name 'other' does not match folder 'bad'",
        "skills/misc/empty/SKILL.md: SKILL.md not found",
    ]


def test_load_all_rejects_stray_skill(tmp_path):
    make_skill(tmp_path, "good")
    stray = tmp_path / "skills" / "loose"
    stray.mkdir()
    (stray / "SKILL.md").write_text("---\nname: loose\ndescription: x\n---\n", encoding="utf-8")
    _, problems = load_all(tmp_path)
    assert problems == ["skills/loose/SKILL.md: skills must live under a category folder"]


def test_load_all_stray_with_subdirs_reports_once(tmp_path):
    stray = tmp_path / "skills" / "loose"
    stray.mkdir(parents=True)
    (stray / "SKILL.md").write_text("---\nname: loose\ndescription: x\n---\n", encoding="utf-8")
    rules = stray / "rules"
    rules.mkdir()
    (rules / "x.md").write_text("not a skill", encoding="utf-8")
    _, problems = load_all(tmp_path)
    assert problems == ["skills/loose/SKILL.md: skills must live under a category folder"]


def test_load_all_ignores_template(tmp_path):
    make_skill(tmp_path, "good")
    template = tmp_path / "skills" / "_template"
    template.mkdir()
    (template / "SKILL.md").write_text(
        "---\nname: template\ndescription: x\n---\n", encoding="utf-8"
    )
    skills, problems = load_all(tmp_path)
    assert problems == []
    assert [s.dirname for s in skills] == ["good"]


def test_load_all_rejects_bad_category_name(tmp_path):
    make_skill(tmp_path, "good", category="Bad_Cat")
    _, problems = load_all(tmp_path)
    assert problems == ["skills/Bad_Cat/good/SKILL.md: category 'Bad_Cat' is not kebab-case"]


def test_load_all_rejects_duplicate_names(tmp_path):
    make_skill(tmp_path, "dup", category="a")
    make_skill(tmp_path, "dup", category="b")
    _, problems = load_all(tmp_path)
    assert problems == [
        "skills/a/dup/SKILL.md: duplicate skill name 'dup', also in skills/b/dup",
        "skills/b/dup/SKILL.md: duplicate skill name 'dup', also in skills/a/dup",
    ]


def test_load_all_includes_manifest_problems(tmp_path):
    make_skill(tmp_path, "foo", "name: foo\ndescription: x\nsource: https://x\n")
    write_manifest_file(tmp_path, {"misc/gone": {"repo": "r", "path": "p", "ref": "main"}})
    _, problems = load_all(tmp_path)
    assert problems == [
        "vendor.json: 'misc/gone' has no skill folder",
        "skills/misc/foo/SKILL.md: has source but no vendor.json entry",
    ]
