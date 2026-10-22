import json

from conftest import (
    commit_all,
    make_bare_registry,
    make_skill,
    make_upstream,
    write_manifest_file,
)
from ferdigheter.cli import main
from ferdigheter.frontmatter import parse_frontmatter


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


def test_cli_add_license_hints(tmp_path, capsys):
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

    argv = [
        "--root",
        str(root),
        "add",
        "misc/bar",
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
        == "skills/misc/bar/LICENSE: no template for WTFPL, add it manually"
    )


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

    make_skill(root, "foo", category="other")
    commit_all(root, "existing foo")
    assert main(base + ["--license", "MIT", "--path", "skills/foo"]) == 1
    assert (
        capsys.readouterr().out == "skills/misc/foo: name 'foo' already used in skills/other/foo\n"
    )
    assert not (root / "vendor.json").exists()
    assert not (root / "skills" / "misc" / "foo").exists()

    root = make_bare_registry(tmp_path / "second")
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
