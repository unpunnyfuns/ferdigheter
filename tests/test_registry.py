import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

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
        {
            "name": "a",
            "category": "c",
            "description": "Has | pipe\nand newline",
            "path": "skills/c/a",
            "tags": ["x", "y"],
        },
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
    registry.write_manifest(
        tmp_path,
        {
            "b/x": {"repo": "r", "path": "p", "ref": "main"},
            "a/y": {"repo": "r", "path": "p", "ref": "main"},
        },
    )
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
        (
            {"Bad Key": {"repo": "r", "path": "p", "ref": "main"}},
            "vendor.json: key 'Bad Key' is not <category>/<name>",
        ),
        (
            {"misc/nope": {"repo": "r", "path": "p", "ref": "main"}},
            "vendor.json: 'misc/nope' has no skill folder",
        ),
        (
            {"misc/foo": {"repo": "r", "path": "p"}},
            "vendor.json: 'misc/foo' needs repo, path and ref",
        ),
        (
            {"misc/foo": {"repo": "", "path": "p", "ref": "main"}},
            "vendor.json: 'misc/foo' needs repo, path and ref",
        ),
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
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")


def commit_all(path: Path, message: str) -> str:
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)
    return git(path, "rev-parse", "HEAD")


UPSTREAM_V1 = (
    "---\nname: foo\ndescription: Upstream v1.\n"
    "license: Complete terms in LICENSE.txt\n---\n\n# Foo v1\n"
)


def make_upstream(
    tmp_path: Path, text: str = UPSTREAM_V1, extra: dict[str, str] | None = None
) -> tuple[str, str]:
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
    merged = registry.merge_frontmatter(
        UPSTREAM_V1, {"license": "MIT", "source": "https://x", "tags": ["a"]}
    )
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
    skill_dir = make_skill(
        tmp_path,
        "foo",
        "name: foo\ndescription: Old.\nlicense: MIT\nsource: https://x\ntags: [a]\n",
    )
    (skill_dir / "LICENSE").write_text("MIT text\n", encoding="utf-8")
    (skill_dir / "stale.md").write_text("old\n", encoding="utf-8")
    upstream = tmp_path / "up"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text(UPSTREAM_V1, encoding="utf-8")
    (upstream / "reference.md").write_text("new\n", encoding="utf-8")
    registry.replace_skill(skill_dir, upstream)
    data, body = registry.parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert data == {
        "name": "foo",
        "description": "Upstream v1.",
        "license": "MIT",
        "source": "https://x",
        "tags": ["a"],
    }
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
    data, _ = registry.parse_frontmatter(
        (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")
    )
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


def make_vendored_repo(tmp_path: Path) -> tuple[Path, str, str]:
    url, sha = make_upstream(tmp_path)
    root = tmp_path / "reg"
    init_repo(root)
    (root / "README.md").write_text(README, encoding="utf-8")
    make_skill(
        root, "foo", "name: foo\ndescription: Old.\nlicense: MIT\nsource: https://x\ntags: [a]\n"
    )
    write_manifest_file(root, {"misc/foo": {"repo": url, "path": "skills/foo", "ref": "main"}})
    registry.main(["--root", str(root), "build"])
    commit_all(root, "vendored")
    return root, url, sha


def test_cli_sync_updates_skill_manifest_and_index(tmp_path, capsys):
    root, _, sha = make_vendored_repo(tmp_path)
    assert registry.main(["--root", str(root), "sync"]) == 0
    assert capsys.readouterr().out == f"misc/foo: none -> {sha[:7]}\n"
    data, _ = registry.parse_frontmatter(
        (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")
    )
    assert data == {
        "name": "foo",
        "description": "Upstream v1.",
        "license": "MIT",
        "source": "https://x",
        "tags": ["a"],
    }
    manifest = json.loads((root / "vendor.json").read_text(encoding="utf-8"))
    assert manifest["misc/foo"]["commit"] == sha
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert index["skills"][0]["description"] == "Upstream v1."


def test_cli_sync_check_reports_newer_upstream(tmp_path, capsys):
    root, _, sha = make_vendored_repo(tmp_path)
    registry.main(["--root", str(root), "sync"])
    commit_all(root, "synced")
    capsys.readouterr()
    assert registry.main(["--root", str(root), "sync", "--check"]) == 0
    assert capsys.readouterr().out == ""
    upstream = tmp_path / "upstream"
    (upstream / "skills" / "foo" / "SKILL.md").write_text(
        UPSTREAM_V1.replace("v1", "v2"), encoding="utf-8"
    )
    new_sha = commit_all(upstream, "v2")
    assert registry.main(["--root", str(root), "sync", "--check"]) == 1
    assert capsys.readouterr().out == f"misc/foo: {sha[:7]} -> {new_sha[:7]}\n"
    assert "v1" in (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")


def test_cli_sync_refuses_dirty_skill(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    (root / "skills" / "misc" / "foo" / "SKILL.md").write_text(
        "---\nname: foo\ndescription: edited\n---\n", encoding="utf-8"
    )
    assert registry.main(["--root", str(root), "sync"]) == 1
    assert capsys.readouterr().out == "skills/misc/foo: has uncommitted changes\n"


def test_cli_sync_unknown_key(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    assert registry.main(["--root", str(root), "sync", "misc/nope"]) == 1
    assert capsys.readouterr().out == "vendor.json: unknown key 'misc/nope'\n"


def test_cli_sync_reports_git_failure(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    write_manifest_file(
        root,
        {"misc/foo": {"repo": f"file://{tmp_path}/missing", "path": "skills/foo", "ref": "main"}},
    )
    commit_all(root, "bad repo")
    assert registry.main(["--root", str(root), "sync"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("misc/foo: git clone failed: ")


def test_merge_frontmatter_keeps_registry_name_in_place():
    merged = registry.merge_frontmatter(
        UPSTREAM_V1, {"name": "vercel-foo", "license": "MIT", "source": "https://x", "tags": ["a"]}
    )
    data, body = registry.parse_frontmatter(merged)
    assert list(data) == ["name", "description", "license", "source", "tags"]
    assert data["name"] == "vercel-foo"
    assert body == "\n# Foo v1\n"


def test_replace_skill_keeps_registry_name(tmp_path):
    skill_dir = make_skill(
        tmp_path,
        "vercel-foo",
        "name: vercel-foo\ndescription: Old.\nlicense: MIT\nsource: https://x\ntags: [a]\n",
    )
    upstream = tmp_path / "up"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text(UPSTREAM_V1, encoding="utf-8")
    registry.replace_skill(skill_dir, upstream)
    data, _ = registry.parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert list(data) == ["name", "description", "license", "source", "tags"]
    assert data["name"] == "vercel-foo"
    assert data["description"] == "Upstream v1."


@pytest.mark.parametrize(
    "key, entry, message",
    [
        (
            "misc/foo",
            {"repo": "r", "path": "p"},
            "vendor.json: 'misc/foo' needs repo, path and ref",
        ),
        ("misc/foo", "nope", "vendor.json: 'misc/foo' needs repo, path and ref"),
        (
            "misc/foo",
            {"repo": "r", "path": "../x", "ref": "main"},
            "vendor.json: 'misc/foo' path must be a relative path inside the repo",
        ),
        (
            "misc/foo",
            {"repo": "r", "path": "/etc", "ref": "main"},
            "vendor.json: 'misc/foo' path must be a relative path inside the repo",
        ),
        (
            "../docs",
            {"repo": "r", "path": "p", "ref": "main"},
            "vendor.json: key '../docs' is not <category>/<name>",
        ),
    ],
)
def test_sync_entry_problems(key, entry, message):
    assert registry._sync_entry_problems(key, entry) == [message]


def test_sync_entry_problems_accepts_nested_path():
    assert (
        registry._sync_entry_problems("misc/foo", {"repo": "r", "path": "a/b", "ref": "main"}) == []
    )


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize(
    "manifest, message",
    [
        (
            {"misc/foo": {"repo": "r", "path": "p"}},
            "vendor.json: 'misc/foo' needs repo, path and ref",
        ),
        ({"misc/foo": "nope"}, "vendor.json: 'misc/foo' needs repo, path and ref"),
        (
            {"misc/foo": {"repo": "r", "path": "../x", "ref": "main"}},
            "vendor.json: 'misc/foo' path must be a relative path inside the repo",
        ),
        (
            {"misc/foo": {"repo": "r", "path": "/etc", "ref": "main"}},
            "vendor.json: 'misc/foo' path must be a relative path inside the repo",
        ),
        (
            {"../docs": {"repo": "r", "path": "p", "ref": "main"}},
            "vendor.json: key '../docs' is not <category>/<name>",
        ),
    ],
)
def test_cli_sync_rejects_bad_entry(tmp_path, capsys, manifest, message, check):
    root, _, _ = make_vendored_repo(tmp_path)
    before = (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")
    write_manifest_file(root, manifest)
    argv = ["--root", str(root), "sync"] + (["--check"] if check else [])
    assert registry.main(argv) == 1
    assert capsys.readouterr().out == f"{message}\n"
    assert (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "check, failure",
    [(False, "misc/foo: git clone failed: "), (True, "misc/foo: git ls-remote failed: ")],
)
def test_cli_sync_repo_cannot_smuggle_git_option(tmp_path, capsys, check, failure):
    root, _, _ = make_vendored_repo(tmp_path)
    write_manifest_file(
        root,
        {"misc/foo": {"repo": "--upload-pack=/nonexistent", "path": "skills/foo", "ref": "main"}},
    )
    commit_all(root, "option-like repo")
    argv = ["--root", str(root), "sync"] + (["--check"] if check else [])
    assert registry.main(argv) == 1
    assert capsys.readouterr().out.startswith(failure)


def test_cli_sync_annotated_tag(tmp_path, capsys):
    root, url, sha = make_vendored_repo(tmp_path)
    git(tmp_path / "upstream", "tag", "-a", "v1", "-m", "v1")
    write_manifest_file(root, {"misc/foo": {"repo": url, "path": "skills/foo", "ref": "v1"}})
    commit_all(root, "pin v1")
    assert registry.main(["--root", str(root), "sync"]) == 0
    assert capsys.readouterr().out == f"misc/foo: none -> {sha[:7]}\n"
    commit_all(root, "synced")
    assert registry.main(["--root", str(root), "sync", "--check"]) == 0
    assert capsys.readouterr().out == ""


def test_remote_commit_prefers_branch_over_same_name_tag(tmp_path):
    url, old_sha = make_upstream(tmp_path)
    upstream = tmp_path / "upstream"
    git(upstream, "tag", "dup")
    (upstream / "skills" / "foo" / "SKILL.md").write_text(
        UPSTREAM_V1.replace("v1", "v2"), encoding="utf-8"
    )
    new_sha = commit_all(upstream, "v2")
    git(upstream, "branch", "dup")
    assert registry.remote_commit(url, "dup") == new_sha
    assert new_sha != old_sha


def test_sync_skill_bad_upstream_frontmatter_keeps_old_folder(tmp_path):
    url, _ = make_upstream(tmp_path, "---\nname: foo\ndescription: Broken.\n")
    root = tmp_path / "reg"
    skill_dir = make_skill(root, "foo", "name: foo\ndescription: Old.\nlicense: MIT\n")
    (skill_dir / "extra.md").write_text("keep\n", encoding="utf-8")
    entry = {"repo": url, "path": "skills/foo", "ref": "main"}
    with pytest.raises(registry.FrontmatterError, match="unterminated"):
        registry.sync_skill(root, "misc/foo", entry)
    assert (skill_dir / "extra.md").read_text(encoding="utf-8") == "keep\n"
    data, _ = registry.parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert data["description"] == "Old."


def test_cli_sync_without_manifest_writes_nothing(tmp_path, capsys):
    make_repo(tmp_path)
    assert registry.main(["--root", str(tmp_path), "sync"]) == 0
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "vendor.json").exists()


def test_cli_sync_refuses_untracked_file_in_subdir(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    rules = root / "skills" / "misc" / "foo" / "rules"
    rules.mkdir()
    (rules / "extra.md").write_text("new\n", encoding="utf-8")
    assert registry.main(["--root", str(root), "sync"]) == 1
    assert capsys.readouterr().out == "skills/misc/foo: has uncommitted changes\n"
