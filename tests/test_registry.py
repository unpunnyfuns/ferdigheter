import pytest
from pathlib import Path
from datetime import date
import json

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


def make_skill(
    root: Path,
    name: str,
    frontmatter: str = VALID,
    body: str = "# Foo\n",
    category: str = "misc",
) -> Path:
    if frontmatter == VALID:
        frontmatter = frontmatter.replace("foo", name)
    skill_dir = root / "skills" / category / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return skill_dir


def test_load_skill(tmp_path):
    skill_dir = make_skill(tmp_path, "foo")
    skill = registry.load_skill(skill_dir)
    assert skill == registry.Skill("misc", "foo", {"name": "foo", "description": "Does foo."})


def test_load_skill_missing_file(tmp_path):
    skill_dir = tmp_path / "skills" / "misc" / "foo"
    skill_dir.mkdir(parents=True)
    with pytest.raises(registry.FrontmatterError, match="SKILL.md not found"):
        registry.load_skill(skill_dir)


def test_discover_sorted_and_skips_underscore(tmp_path):
    make_skill(tmp_path, "zeta", category="b")
    make_skill(tmp_path, "alpha", category="b")
    make_skill(tmp_path, "mid", category="a")
    make_skill(tmp_path, "_draft", category="a")
    (tmp_path / "skills" / "_template").mkdir()
    (tmp_path / "skills" / "_template" / "SKILL.md").write_text("---\nname: x\n---\n")
    (tmp_path / "skills" / "empty-category").mkdir()
    found = [(p.parent.name, p.name) for p in registry.discover(tmp_path)]
    assert found == [("a", "mid"), ("b", "alpha"), ("b", "zeta")]


def test_discover_no_skills_dir(tmp_path):
    assert registry.discover(tmp_path) == []


def test_validate_valid():
    assert (
        registry.validate_skill(registry.Skill("misc", "foo", {"name": "foo", "description": "x"}))
        == []
    )


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
    assert registry.validate_skill(registry.Skill("misc", "foo", data)) == []


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
    problems = registry.validate_skill(registry.Skill("misc", dirname, data))
    assert any(message in p for p in problems), problems


def test_load_all_prefixes_problems(tmp_path):
    make_skill(tmp_path, "good")
    make_skill(tmp_path, "bad", "name: other\ndescription: x\n")
    (tmp_path / "skills" / "misc" / "empty").mkdir()
    skills, problems = registry.load_all(tmp_path)
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
    _, problems = registry.load_all(tmp_path)
    assert problems == ["skills/loose/SKILL.md: skills must live under a category folder"]


def test_load_all_rejects_bad_category_name(tmp_path):
    make_skill(tmp_path, "good", category="Bad_Cat")
    _, problems = registry.load_all(tmp_path)
    assert problems == ["skills/Bad_Cat/good/SKILL.md: category 'Bad_Cat' is not kebab-case"]


def test_load_all_rejects_duplicate_names(tmp_path):
    make_skill(tmp_path, "dup", category="a")
    make_skill(tmp_path, "dup", category="b")
    _, problems = registry.load_all(tmp_path)
    assert problems == [
        "skills/a/dup/SKILL.md: duplicate skill name 'dup', also in skills/b/dup",
        "skills/b/dup/SKILL.md: duplicate skill name 'dup', also in skills/a/dup",
    ]


def test_build_index_sorts_and_omits_optional():
    skills = [
        registry.Skill("misc", "zeta", {"name": "zeta", "description": " Z \n"}),
        registry.Skill(
            "misc",
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
                "category": "misc",
                "description": "A",
                "path": "skills/misc/alpha",
                "license": "MIT",
                "source": "https://x",
                "tags": ["t"],
                "metadata": {"v": "1"},
            },
            {
                "name": "zeta",
                "category": "misc",
                "description": "Z",
                "path": "skills/misc/zeta",
            },
        ],
    }


def test_render_table():
    entries = [
        {"name": "a", "category": "c", "description": "Has | pipe\nand newline", "path": "skills/c/a", "tags": ["x", "y"]},
        {"name": "b", "category": "c", "description": "Plain", "path": "skills/c/b"},
    ]
    assert registry.render_table(entries) == (
        "| Skill | Description | Tags |\n"
        "|---|---|---|\n"
        "| [a](skills/c/a/) | Has \\| pipe and newline | x, y |\n"
        "| [b](skills/c/b/) | Plain |  |"
    )


def test_render_sections_groups_by_category():
    entries = [
        {"name": "a", "category": "web", "description": "A", "path": "skills/web/a"},
        {"name": "b", "category": "process", "description": "B", "path": "skills/process/b"},
        {"name": "c", "category": "web", "description": "C", "path": "skills/web/c"},
    ]
    assert registry.render_sections(entries) == (
        "### process\n\n"
        "| Skill | Description | Tags |\n|---|---|---|\n"
        "| [b](skills/process/b/) | B |  |\n"
        "\n"
        "### web\n\n"
        "| Skill | Description | Tags |\n|---|---|---|\n"
        "| [a](skills/web/a/) | A |  |\n"
        "| [c](skills/web/c/) | C |  |"
    )


def test_splice_readme_replaces_between_markers():
    text = "# T\n\nintro\n\n<!-- index:start -->\nold\n<!-- index:end -->\n\nfooter\n"
    out = registry.splice_readme(text, "TABLE")
    assert out == "# T\n\nintro\n\n<!-- index:start -->\nTABLE\n<!-- index:end -->\n\nfooter\n"


def test_splice_readme_missing_markers():
    with pytest.raises(ValueError, match="markers"):
        registry.splice_readme("# T\n", "TABLE")


README = "# Reg\n\n<!-- index:start -->\n<!-- index:end -->\n"


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    make_skill(tmp_path, "foo", "name: foo\ndescription: Does foo.\ntags: [x]\n")
    return tmp_path


def test_cli_validate_ok(tmp_path, capsys):
    make_repo(tmp_path)
    assert registry.main(["--root", str(tmp_path), "validate"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_validate_reports_problems(tmp_path, capsys):
    make_repo(tmp_path)
    make_skill(tmp_path, "bad", "name: nope\ndescription: x\n")
    assert registry.main(["--root", str(tmp_path), "validate"]) == 1
    assert (
        capsys.readouterr().out
        == "skills/misc/bad/SKILL.md: name 'nope' does not match folder 'bad'\n"
    )


def test_cli_build_writes_outputs(tmp_path, capsys):
    make_repo(tmp_path)
    assert registry.main(["--root", str(tmp_path), "build"]) == 0
    assert capsys.readouterr().out == ""
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["generated"] == date.today().isoformat()
    assert index["skills"][0]["name"] == "foo"
    assert (tmp_path / "index.json").read_text(encoding="utf-8").endswith("}\n")
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "### misc\n\n| Skill |" in readme
    assert "| [foo](skills/misc/foo/) | Does foo. | x |" in readme
    assert index["skills"][0]["category"] == "misc"


def test_cli_build_refuses_on_problems(tmp_path):
    make_repo(tmp_path)
    make_skill(tmp_path, "bad", "name: nope\ndescription: x\n")
    assert registry.main(["--root", str(tmp_path), "build"]) == 1
    assert not (tmp_path / "index.json").exists()


def test_cli_build_missing_markers(tmp_path, capsys):
    make_repo(tmp_path)
    (tmp_path / "README.md").write_text("# no markers\n", encoding="utf-8")
    assert registry.main(["--root", str(tmp_path), "build"]) == 1
    assert capsys.readouterr().out == "README.md: missing index markers\n"


def test_cli_build_check(tmp_path, capsys):
    make_repo(tmp_path)
    assert registry.main(["--root", str(tmp_path), "build", "--check"]) == 1
    assert capsys.readouterr().out == "index.json is out of date\nREADME.md is out of date\n"
    assert not (tmp_path / "index.json").exists()

    registry.main(["--root", str(tmp_path), "build"])
    assert registry.main(["--root", str(tmp_path), "build", "--check"]) == 0

    make_skill(tmp_path, "bar")
    assert registry.main(["--root", str(tmp_path), "build", "--check"]) == 1


def test_cli_build_check_keeps_existing_date(tmp_path):
    make_repo(tmp_path)
    registry.main(["--root", str(tmp_path), "build"])
    index_path = tmp_path / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["generated"] = "2000-01-01"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert registry.main(["--root", str(tmp_path), "build", "--check"]) == 0
