import json
from datetime import date

import pytest

from conftest import (
    UPSTREAM_V1,
    commit_all,
    git,
    make_bare_registry,
    make_repo,
    make_skill,
    make_upstream,
    make_vendored_repo,
    write_manifest_file,
)
from ferdigheter.cli import main
from ferdigheter.commands import _sync_entry_problems
from ferdigheter.frontmatter import parse_frontmatter


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
    assert _sync_entry_problems(key, entry) == [message]


def test_sync_entry_problems_accepts_nested_path():
    assert _sync_entry_problems("misc/foo", {"repo": "r", "path": "a/b", "ref": "main"}) == []


def test_cli_validate_ok(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "validate"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_validate_reports_problems(tmp_path, capsys):
    make_repo(tmp_path)
    make_skill(tmp_path, "bad", "name: nope\ndescription: x\n")
    assert main(["--root", str(tmp_path), "validate"]) == 1
    assert (
        capsys.readouterr().out
        == "skills/misc/bad/SKILL.md: name 'nope' does not match folder 'bad'\n"
    )


def test_cli_build_writes_outputs(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "build"]) == 0
    assert capsys.readouterr().out == ""
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["generated"] == date.today().isoformat()
    assert index["skills"][0]["name"] == "foo"
    assert (tmp_path / "index.json").read_text(encoding="utf-8").endswith("}\n")
    catalog = (tmp_path / "CATALOG.md").read_text(encoding="utf-8")
    assert "### misc\n\n| Skill |" in catalog
    assert "| [foo](skills/misc/foo/) | Does foo. | x |" in catalog
    assert index["skills"][0]["category"] == "misc"


def test_cli_build_refuses_on_problems(tmp_path):
    make_repo(tmp_path)
    make_skill(tmp_path, "bad", "name: nope\ndescription: x\n")
    assert main(["--root", str(tmp_path), "build"]) == 1
    assert not (tmp_path / "index.json").exists()


def test_cli_build_missing_markers(tmp_path, capsys):
    make_repo(tmp_path)
    (tmp_path / "CATALOG.md").write_text("# no markers\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "build"]) == 1
    assert capsys.readouterr().out == "CATALOG.md: missing index markers\n"


def test_cli_build_check(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "build", "--check"]) == 1
    assert capsys.readouterr().out == "index.json is out of date\nCATALOG.md is out of date\n"
    assert not (tmp_path / "index.json").exists()

    main(["--root", str(tmp_path), "build"])
    assert main(["--root", str(tmp_path), "build", "--check"]) == 0

    make_skill(tmp_path, "bar")
    assert main(["--root", str(tmp_path), "build", "--check"]) == 1


def test_cli_build_check_keeps_existing_date(tmp_path):
    make_repo(tmp_path)
    main(["--root", str(tmp_path), "build"])
    index_path = tmp_path / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["generated"] = "2000-01-01"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "build", "--check"]) == 0


def test_cli_sync_updates_skill_manifest_and_index(tmp_path, capsys):
    root, _, sha = make_vendored_repo(tmp_path)
    assert main(["--root", str(root), "sync"]) == 0
    assert capsys.readouterr().out == f"misc/foo: none -> {sha[:7]}\n"
    data, _ = parse_frontmatter(
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
    main(["--root", str(root), "sync"])
    commit_all(root, "synced")
    capsys.readouterr()
    assert main(["--root", str(root), "sync", "--check"]) == 0
    assert capsys.readouterr().out == ""
    upstream = tmp_path / "upstream"
    (upstream / "skills" / "foo" / "SKILL.md").write_text(
        UPSTREAM_V1.replace("v1", "v2"), encoding="utf-8"
    )
    new_sha = commit_all(upstream, "v2")
    assert main(["--root", str(root), "sync", "--check"]) == 1
    assert capsys.readouterr().out == f"misc/foo: {sha[:7]} -> {new_sha[:7]}\n"
    assert "v1" in (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")


def test_cli_sync_annotated_tag(tmp_path, capsys):
    root, url, sha = make_vendored_repo(tmp_path)
    git(tmp_path / "upstream", "tag", "-a", "v1", "-m", "v1")
    write_manifest_file(root, {"misc/foo": {"repo": url, "path": "skills/foo", "ref": "v1"}})
    commit_all(root, "pin v1")
    assert main(["--root", str(root), "sync"]) == 0
    assert capsys.readouterr().out == f"misc/foo: none -> {sha[:7]}\n"
    commit_all(root, "synced")
    assert main(["--root", str(root), "sync", "--check"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_sync_refuses_dirty_skill(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    (root / "skills" / "misc" / "foo" / "SKILL.md").write_text(
        "---\nname: foo\ndescription: edited\n---\n", encoding="utf-8"
    )
    assert main(["--root", str(root), "sync"]) == 1
    assert capsys.readouterr().out == "skills/misc/foo: has uncommitted changes\n"


def test_cli_sync_refuses_untracked_file_in_subdir(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    rules = root / "skills" / "misc" / "foo" / "rules"
    rules.mkdir()
    (rules / "extra.md").write_text("new\n", encoding="utf-8")
    assert main(["--root", str(root), "sync"]) == 1
    assert capsys.readouterr().out == "skills/misc/foo: has uncommitted changes\n"


def test_cli_sync_unknown_key(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    assert main(["--root", str(root), "sync", "misc/nope"]) == 1
    assert capsys.readouterr().out == "vendor.json: unknown key 'misc/nope'\n"


def test_cli_sync_rejects_bad_entry(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    before = (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")
    write_manifest_file(root, {"misc/foo": {"repo": "r", "path": "../x", "ref": "main"}})
    assert main(["--root", str(root), "sync"]) == 1
    assert (
        capsys.readouterr().out
        == "vendor.json: 'misc/foo' path must be a relative path inside the repo\n"
    )
    assert (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8") == before


def test_cli_sync_reports_git_failure(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    write_manifest_file(
        root,
        {"misc/foo": {"repo": f"file://{tmp_path}/missing", "path": "skills/foo", "ref": "main"}},
    )
    commit_all(root, "bad repo")
    assert main(["--root", str(root), "sync"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("misc/foo: git clone failed: ")


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
    assert main(argv) == 1
    assert capsys.readouterr().out.startswith(failure)


def test_cli_sync_without_manifest_writes_nothing(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "sync"]) == 0
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "vendor.json").exists()


def test_cli_add_vendors_skill(tmp_path, capsys):
    url, sha = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
        "--tags",
        "a,b",
        "--copyright",
        "2025 Up",
    ]
    assert main(argv) == 0
    assert (
        capsys.readouterr().out == f"misc/foo: none -> {sha[:7]}\nwrote skills/misc/foo/LICENSE\n"
    )
    skill_md = root / "skills" / "misc" / "foo" / "SKILL.md"
    data, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    assert data == {
        "name": "foo",
        "description": "Upstream v1.",
        "license": "MIT",
        "source": url,
        "tags": ["a", "b"],
    }
    assert (
        (root / "skills" / "misc" / "foo" / "LICENSE")
        .read_text(encoding="utf-8")
        .startswith("MIT License\n\nCopyright (c) 2025 Up\n")
    )
    manifest = json.loads((root / "vendor.json").read_text(encoding="utf-8"))
    assert manifest["misc/foo"] == {"repo": url, "path": "skills/foo", "ref": "main", "commit": sha}
    assert "| [foo](skills/misc/foo/) | Upstream v1. | a, b |" in (root / "CATALOG.md").read_text(
        encoding="utf-8"
    )
    assert main(["--root", str(root), "validate"]) == 0


def test_cli_add_skips_license_when_upstream_has_one(tmp_path, capsys):
    url, _ = make_upstream(tmp_path, extra={"LICENSE.txt": "theirs\n"})
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
        "--copyright",
        "x",
    ]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "wrote" not in out
    assert "LICENSE:" not in out
    assert not (root / "skills" / "misc" / "foo" / "LICENSE").exists()
    skill_md = root / "skills" / "misc" / "foo" / "SKILL.md"
    data, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    assert "tags" not in data


def test_cli_add_hint_when_copyright_missing(tmp_path, capsys):
    url, _ = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
    ]
    assert main(argv) == 0
    assert (
        capsys.readouterr().out.splitlines()[1]
        == "skills/misc/foo/LICENSE: not written, pass --copyright"
    )


def test_cli_add_hint_when_no_template(tmp_path, capsys):
    url, _ = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "WTFPL",
    ]
    assert main(argv) == 0
    assert (
        capsys.readouterr().out.splitlines()[1]
        == "skills/misc/foo/LICENSE: no template for WTFPL, add it manually"
    )


def test_cli_add_sets_name_from_key(tmp_path, capsys):
    url, _ = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/vercel-foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
        "--copyright",
        "2025 Up",
    ]
    assert main(argv) == 0
    skill_md = root / "skills" / "misc" / "vercel-foo" / "SKILL.md"
    data, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    assert data["name"] == "vercel-foo"
    capsys.readouterr()
    assert main(["--root", str(root), "validate"]) == 0
    assert "| [vercel-foo](skills/misc/vercel-foo/) |" in (root / "CATALOG.md").read_text(
        encoding="utf-8"
    )


def test_cli_add_rejects_existing_key_and_folder(tmp_path, capsys):
    url, _ = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
        "--copyright",
        "x",
    ]
    assert main(argv) == 0
    commit_all(root, "added")
    capsys.readouterr()
    assert main(argv) == 1
    assert capsys.readouterr().out == "vendor.json: 'misc/foo' already exists\n"
    write_manifest_file(root, {})
    assert main(argv) == 1
    assert capsys.readouterr().out == "skills/misc/foo: already exists\n"


def test_cli_add_reports_pre_check_problems(tmp_path, capsys):
    url, _ = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    base = ["--root", str(root), "add", "misc/foo", "--repo", url]
    assert main(base + ["--license", "MIT", "--path", "../x"]) == 1
    assert (
        capsys.readouterr().out
        == "vendor.json: 'misc/foo' path must be a relative path inside the repo\n"
    )
    assert main(base + ["--license", "MIT", "--path", "skills/foo", "--tags", "Bad Tag"]) == 1
    assert capsys.readouterr().out == "tags must be kebab-case, comma-separated\n"
    assert main(base + ["--license", "", "--path", "skills/foo"]) == 1
    assert capsys.readouterr().out == "license must be a non-empty string\n"
    assert not (root / "vendor.json").exists()
    assert not (root / "skills" / "misc" / "foo").exists()


def test_cli_add_rejects_name_used_in_another_category(tmp_path, capsys):
    url, _ = make_upstream(tmp_path)
    root = make_bare_registry(tmp_path)
    make_skill(root, "foo", category="other")
    commit_all(root, "existing foo")
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
    ]
    assert main(argv) == 1
    assert (
        capsys.readouterr().out == "skills/misc/foo: name 'foo' already used in skills/other/foo\n"
    )
    assert not (root / "vendor.json").exists()
    assert not (root / "skills" / "misc" / "foo").exists()


def test_cli_add_git_failure_leaves_no_manifest_entry(tmp_path, capsys):
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        f"file://{tmp_path}/missing",
        "--path",
        "skills/foo",
        "--license",
        "MIT",
    ]
    assert main(argv) == 1
    assert capsys.readouterr().out.startswith("misc/foo: git clone failed: ")
    assert not (root / "vendor.json").exists()


def test_cli_add_prints_cleanup_hint_when_build_fails(tmp_path, capsys):
    text = "---\nname: foo\ndescription: " + "x" * 1025 + "\n---\n\n# Foo\n"
    url, _ = make_upstream(tmp_path, text=text)
    root = make_bare_registry(tmp_path)
    argv = [
        "--root",
        str(root),
        "add",
        "misc/foo",
        "--repo",
        url,
        "--path",
        "skills/foo",
        "--license",
        "MIT",
        "--copyright",
        "2025 Up",
    ]
    assert main(argv) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == (
        "skills/misc/foo: added but validation failed; clean up with: "
        "rm -rf skills/misc/foo and remove the entry from vendor.json"
    )
