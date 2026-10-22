import json

import pytest

from conftest import (
    UPSTREAM_V1,
    commit_all,
    git,
    make_repo,
    make_vendored_repo,
    write_manifest_file,
)
from ferdigheter.cli import main
from ferdigheter.frontmatter import parse_frontmatter


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

    root, _, _ = make_vendored_repo(tmp_path / "subdir")
    rules = root / "skills" / "misc" / "foo" / "rules"
    rules.mkdir()
    (rules / "extra.md").write_text("new\n", encoding="utf-8")
    assert main(["--root", str(root), "sync"]) == 1
    assert capsys.readouterr().out == "skills/misc/foo: has uncommitted changes\n"


def test_cli_sync_reports_pre_check_problems(tmp_path, capsys):
    root, _, _ = make_vendored_repo(tmp_path)
    before = (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")

    assert main(["--root", str(root), "sync", "misc/nope"]) == 1
    assert capsys.readouterr().out == "vendor.json: unknown key 'misc/nope'\n"
    assert (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8") == before

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
