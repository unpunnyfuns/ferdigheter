import pytest
from pathlib import Path
from datetime import date
import json
import subprocess

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


def test_load_all_stray_with_subdirs_reports_once(tmp_path):
    stray = tmp_path / "skills" / "loose"
    stray.mkdir(parents=True)
    (stray / "SKILL.md").write_text("---\nname: loose\ndescription: x\n---\n", encoding="utf-8")
    rules = stray / "rules"
    rules.mkdir()
    (rules / "x.md").write_text("not a skill", encoding="utf-8")
    _, problems = registry.load_all(tmp_path)
    assert problems == ["skills/loose/SKILL.md: skills must live under a category folder"]


def test_load_all_ignores_template(tmp_path):
    make_skill(tmp_path, "good")
    template = tmp_path / "skills" / "_template"
    template.mkdir()
    (template / "SKILL.md").write_text(
        "---\nname: template\ndescription: x\n---\n", encoding="utf-8"
    )
    skills, problems = registry.load_all(tmp_path)
    assert problems == []
    assert [s.dirname for s in skills] == ["good"]


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


def test_render_sections_empty():
    assert registry.render_sections([]) == ""


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


def write_manifest_file(root: Path, manifest) -> None:
    (root / "vendor.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_load_manifest_missing_is_empty(tmp_path):
    assert registry.load_manifest(tmp_path) == ({}, [])


def test_load_manifest_invalid_json(tmp_path):
    (tmp_path / "vendor.json").write_text("{", encoding="utf-8")
    manifest, problems = registry.load_manifest(tmp_path)
    assert manifest == {}
    assert problems[0].startswith("vendor.json: invalid json:")


def test_load_manifest_not_object(tmp_path):
    write_manifest_file(tmp_path, [])
    assert registry.load_manifest(tmp_path) == ({}, ["vendor.json: must be a JSON object"])


def test_write_manifest_sorts_keys(tmp_path):
    registry.write_manifest(tmp_path, {"b/x": {"repo": "r", "path": "p", "ref": "main"}, "a/y": {"repo": "r", "path": "p", "ref": "main"}})
    text = (tmp_path / "vendor.json").read_text(encoding="utf-8")
    assert text.startswith('{\n  "a/y": {')
    assert text.endswith("}\n")


def test_validate_manifest_ok(tmp_path):
    make_skill(tmp_path, "foo", "name: foo\ndescription: x\nsource: https://x\n")
    skills, _ = registry.load_all(tmp_path)
    manifest = {"misc/foo": {"repo": "https://x", "path": "skills/foo", "ref": "main"}}
    assert registry.validate_manifest(tmp_path, manifest, skills) == []


@pytest.mark.parametrize(
    "manifest, message",
    [
        ({"Bad Key": {"repo": "r", "path": "p", "ref": "main"}}, "vendor.json: key 'Bad Key' is not <category>/<name>"),
        ({"misc/nope": {"repo": "r", "path": "p", "ref": "main"}}, "vendor.json: 'misc/nope' has no skill folder"),
        ({"misc/foo": {"repo": "r", "path": "p"}}, "vendor.json: 'misc/foo' needs repo, path and ref"),
        ({"misc/foo": {"repo": "", "path": "p", "ref": "main"}}, "vendor.json: 'misc/foo' needs repo, path and ref"),
        ({"misc/foo": "nope"}, "vendor.json: 'misc/foo' needs repo, path and ref"),
    ],
)
def test_validate_manifest_problems(tmp_path, manifest, message):
    make_skill(tmp_path, "foo")
    skills, _ = registry.load_all(tmp_path)
    assert message in registry.validate_manifest(tmp_path, manifest, skills)


def test_validate_manifest_source_without_entry(tmp_path):
    make_skill(tmp_path, "foo", "name: foo\ndescription: x\nsource: https://x\n")
    skills, _ = registry.load_all(tmp_path)
    assert registry.validate_manifest(tmp_path, {}, skills) == [
        "skills/misc/foo/SKILL.md: has source but no vendor.json entry"
    ]


def test_load_all_includes_manifest_problems(tmp_path):
    make_skill(tmp_path, "foo", "name: foo\ndescription: x\nsource: https://x\n")
    write_manifest_file(tmp_path, {"misc/gone": {"repo": "r", "path": "p", "ref": "main"}})
    _, problems = registry.load_all(tmp_path)
    assert problems == [
        "vendor.json: 'misc/gone' has no skill folder",
        "skills/misc/foo/SKILL.md: has source but no vendor.json entry",
    ]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")


def commit_all(path: Path, message: str) -> str:
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)
    return git(path, "rev-parse", "HEAD")


UPSTREAM_V1 = "---\nname: foo\ndescription: Upstream v1.\nlicense: Complete terms in LICENSE.txt\n---\n\n# Foo v1\n"


def make_upstream(tmp_path: Path, text: str = UPSTREAM_V1, extra: dict[str, str] | None = None) -> tuple[str, str]:
    repo = tmp_path / "upstream"
    init_repo(repo)
    skill = repo / "skills" / "foo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(text, encoding="utf-8")
    for name, content in (extra or {}).items():
        (skill / name).write_text(content, encoding="utf-8")
    sha = commit_all(repo, "v1")
    return f"file://{repo}", sha


def test_dump_frontmatter_round_trip():
    text = "---\nname: foo\ndescription: 'Quoted: yes'\ntags:\n- a\n---\n\n# Body\n"
    data, body = registry.parse_frontmatter(text)
    assert registry.parse_frontmatter(registry.dump_frontmatter(data, body)) == (data, body)


def test_merge_frontmatter_appends_registry_fields_last():
    merged = registry.merge_frontmatter(UPSTREAM_V1, {"license": "MIT", "source": "https://x", "tags": ["a"]})
    data, body = registry.parse_frontmatter(merged)
    assert list(data) == ["name", "description", "license", "source", "tags"]
    assert data["license"] == "MIT"
    assert body == "\n# Foo v1\n"


def test_merge_frontmatter_without_overrides_drops_upstream_registry_fields():
    data, _ = registry.parse_frontmatter(registry.merge_frontmatter(UPSTREAM_V1, {}))
    assert "license" not in data


def test_fetch_upstream_and_remote_commit(tmp_path):
    url, sha = make_upstream(tmp_path)
    dest = tmp_path / "clone"
    assert registry.fetch_upstream(url, "main", dest) == sha
    assert (dest / "skills" / "foo" / "SKILL.md").is_file()
    assert registry.remote_commit(url, "main") == sha


def test_remote_commit_unknown_ref(tmp_path):
    url, _ = make_upstream(tmp_path)
    with pytest.raises(subprocess.CalledProcessError):
        registry.remote_commit(url, "nope")


def test_replace_skill_keeps_registry_fields_and_license(tmp_path):
    skill_dir = make_skill(tmp_path, "foo", "name: foo\ndescription: Old.\nlicense: MIT\nsource: https://x\ntags: [a]\n")
    (skill_dir / "LICENSE").write_text("MIT text\n", encoding="utf-8")
    (skill_dir / "stale.md").write_text("old\n", encoding="utf-8")
    upstream = tmp_path / "up"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text(UPSTREAM_V1, encoding="utf-8")
    (upstream / "reference.md").write_text("new\n", encoding="utf-8")
    registry.replace_skill(skill_dir, upstream)
    data, body = registry.parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert data == {"name": "foo", "description": "Upstream v1.", "license": "MIT", "source": "https://x", "tags": ["a"]}
    assert body == "\n# Foo v1\n"
    assert (skill_dir / "LICENSE").read_text(encoding="utf-8") == "MIT text\n"
    assert (skill_dir / "reference.md").is_file()
    assert not (skill_dir / "stale.md").exists()


def test_replace_skill_prefers_upstream_license(tmp_path):
    skill_dir = make_skill(tmp_path, "foo")
    (skill_dir / "LICENSE").write_text("ours\n", encoding="utf-8")
    upstream = tmp_path / "up"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text(UPSTREAM_V1, encoding="utf-8")
    (upstream / "LICENSE").write_text("theirs\n", encoding="utf-8")
    registry.replace_skill(skill_dir, upstream)
    assert (skill_dir / "LICENSE").read_text(encoding="utf-8") == "theirs\n"


def test_sync_skill_creates_missing_folder(tmp_path):
    url, sha = make_upstream(tmp_path)
    root = tmp_path / "reg"
    root.mkdir()
    entry = {"repo": url, "path": "skills/foo", "ref": "main"}
    assert registry.sync_skill(root, "misc/foo", entry) == sha
    data, _ = registry.parse_frontmatter((root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8"))
    assert data == {"name": "foo", "description": "Upstream v1."}


def test_sync_skill_missing_path(tmp_path):
    url, _ = make_upstream(tmp_path)
    entry = {"repo": url, "path": "skills/nope", "ref": "main"}
    with pytest.raises(FileNotFoundError, match=r"path 'skills/nope' not found in file://.*@main"):
        registry.sync_skill(tmp_path / "reg", "misc/foo", entry)


def test_sync_skill_path_without_skill_md(tmp_path):
    url, _ = make_upstream(tmp_path)
    repo = tmp_path / "upstream"
    (repo / "docs").mkdir()
    (repo / "docs" / "x.md").write_text("x\n", encoding="utf-8")
    commit_all(repo, "docs")
    entry = {"repo": url, "path": "docs", "ref": "main"}
    with pytest.raises(FileNotFoundError, match="path 'docs' has no SKILL.md"):
        registry.sync_skill(tmp_path / "reg", "misc/foo", entry)
