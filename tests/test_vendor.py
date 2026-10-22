import subprocess

import pytest

from conftest import UPSTREAM_V1, commit_all, git, make_skill, make_upstream
from ferdigheter.frontmatter import parse_frontmatter
from ferdigheter.model import FrontmatterError
from ferdigheter.vendor import (
    fetch_upstream,
    has_license_file,
    license_text,
    parse_tags,
    remote_commit,
    replace_skill,
    set_registry_fields,
    sync_skill,
)


def test_fetch_upstream_and_remote_commit(tmp_path):
    url, sha = make_upstream(tmp_path)
    dest = tmp_path / "clone"
    assert fetch_upstream(url, "main", dest) == sha
    assert (dest / "skills" / "foo" / "SKILL.md").is_file()
    assert remote_commit(url, "main") == sha


def test_remote_commit_unknown_ref(tmp_path):
    url, _ = make_upstream(tmp_path)
    with pytest.raises(subprocess.CalledProcessError):
        remote_commit(url, "nope")


def test_remote_commit_prefers_branch_over_same_name_tag(tmp_path):
    url, old_sha = make_upstream(tmp_path)
    upstream = tmp_path / "upstream"
    git(upstream, "tag", "dup")
    (upstream / "skills" / "foo" / "SKILL.md").write_text(
        UPSTREAM_V1.replace("v1", "v2"), encoding="utf-8"
    )
    new_sha = commit_all(upstream, "v2")
    git(upstream, "branch", "dup")
    assert remote_commit(url, "dup") == new_sha
    assert new_sha != old_sha


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
    replace_skill(skill_dir, upstream)
    data, body = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
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
    replace_skill(skill_dir, upstream)
    assert (skill_dir / "LICENSE").read_text(encoding="utf-8") == "theirs\n"


def test_replace_skill_keeps_registry_name(tmp_path):
    skill_dir = make_skill(
        tmp_path,
        "vercel-foo",
        "name: vercel-foo\ndescription: Old.\nlicense: MIT\nsource: https://x\ntags: [a]\n",
    )
    upstream = tmp_path / "up"
    upstream.mkdir()
    (upstream / "SKILL.md").write_text(UPSTREAM_V1, encoding="utf-8")
    replace_skill(skill_dir, upstream)
    data, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert list(data) == ["name", "description", "license", "source", "tags"]
    assert data["name"] == "vercel-foo"
    assert data["description"] == "Upstream v1."


def test_sync_skill_creates_missing_folder(tmp_path):
    url, sha = make_upstream(tmp_path)
    root = tmp_path / "reg"
    root.mkdir()
    entry = {"repo": url, "path": "skills/foo", "ref": "main"}
    assert sync_skill(root, "misc/foo", entry) == sha
    data, _ = parse_frontmatter(
        (root / "skills" / "misc" / "foo" / "SKILL.md").read_text(encoding="utf-8")
    )
    assert data == {"name": "foo", "description": "Upstream v1."}


def test_sync_skill_missing_path(tmp_path):
    url, _ = make_upstream(tmp_path)
    entry = {"repo": url, "path": "skills/nope", "ref": "main"}
    with pytest.raises(FileNotFoundError, match=r"path 'skills/nope' not found in file://.*@main"):
        sync_skill(tmp_path / "reg", "misc/foo", entry)


def test_sync_skill_path_without_skill_md(tmp_path):
    url, _ = make_upstream(tmp_path)
    repo = tmp_path / "upstream"
    (repo / "docs").mkdir()
    (repo / "docs" / "x.md").write_text("x\n", encoding="utf-8")
    commit_all(repo, "docs")
    entry = {"repo": url, "path": "docs", "ref": "main"}
    with pytest.raises(FileNotFoundError, match="path 'docs' has no SKILL.md"):
        sync_skill(tmp_path / "reg", "misc/foo", entry)


def test_sync_skill_bad_upstream_frontmatter_keeps_old_folder(tmp_path):
    url, _ = make_upstream(tmp_path, "---\nname: foo\ndescription: Broken.\n")
    root = tmp_path / "reg"
    skill_dir = make_skill(root, "foo", "name: foo\ndescription: Old.\nlicense: MIT\n")
    (skill_dir / "extra.md").write_text("keep\n", encoding="utf-8")
    entry = {"repo": url, "path": "skills/foo", "ref": "main"}
    with pytest.raises(FrontmatterError, match="unterminated"):
        sync_skill(root, "misc/foo", entry)
    assert (skill_dir / "extra.md").read_text(encoding="utf-8") == "keep\n"
    data, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert data["description"] == "Old."


def test_parse_tags():
    assert parse_tags("a, b-c,,d") == ["a", "b-c", "d"]
    assert parse_tags("") == []


def test_parse_tags_rejects_bad():
    with pytest.raises(ValueError, match="tags must be kebab-case, comma-separated"):
        parse_tags("Bad Tag")


def test_license_text_mit_substitutes():
    text = license_text("MIT", "2025 Someone")
    assert text.startswith("MIT License\n\nCopyright (c) 2025 Someone\n")


def test_license_text_mit_needs_copyright():
    with pytest.raises(ValueError, match="copyright required"):
        license_text("MIT", None)


def test_license_text_apache_verbatim():
    text = license_text("Apache-2.0", None)
    assert "Apache License" in text and "{copyright}" not in text


def test_license_text_unknown():
    assert license_text("WTFPL", "x") is None


def test_license_text_rejects_path_like_spdx():
    assert license_text("../../requirements", "x") is None
    assert license_text("MIT/../x", "x") is None


def test_has_license_file(tmp_path):
    assert not has_license_file(tmp_path)
    (tmp_path / "license.md").write_text("x", encoding="utf-8")
    assert has_license_file(tmp_path)


def test_set_registry_fields(tmp_path):
    skill_dir = make_skill(tmp_path, "foo", "name: foo\ndescription: D.\nlicense: old\n")
    set_registry_fields(
        skill_dir / "SKILL.md", {"license": "MIT", "source": "https://x", "tags": ["a"]}
    )
    data, body = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert data == {
        "name": "foo",
        "description": "D.",
        "license": "MIT",
        "source": "https://x",
        "tags": ["a"],
    }
    assert body == "\n# Foo\n"
