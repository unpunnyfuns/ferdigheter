import pytest

from conftest import make_skill, write_manifest_file
from ferdigheter.commands import _sync_entry_problems
from ferdigheter.manifest import load_manifest, validate_manifest, write_manifest
from ferdigheter.skills import load_all


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


def test_load_manifest_missing_is_empty(tmp_path):
    assert load_manifest(tmp_path) == ({}, [])


def test_load_manifest_invalid_json(tmp_path):
    (tmp_path / "vendor.json").write_text("{", encoding="utf-8")
    manifest, problems = load_manifest(tmp_path)
    assert manifest == {}
    assert problems[0].startswith("vendor.json: invalid json:")


def test_load_manifest_not_object(tmp_path):
    write_manifest_file(tmp_path, [])
    assert load_manifest(tmp_path) == ({}, ["vendor.json: must be a JSON object"])


def test_write_manifest_sorts_keys(tmp_path):
    write_manifest(
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
    skills, _ = load_all(tmp_path)
    manifest = {"misc/foo": {"repo": "https://x", "path": "skills/foo", "ref": "main"}}
    assert validate_manifest(tmp_path, manifest, skills) == []


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
    skills, _ = load_all(tmp_path)
    assert message in validate_manifest(tmp_path, manifest, skills)


def test_validate_manifest_source_without_entry(tmp_path):
    make_skill(tmp_path, "foo", "name: foo\ndescription: x\nsource: https://x\n")
    skills, _ = load_all(tmp_path)
    assert validate_manifest(tmp_path, {}, skills) == [
        "skills/misc/foo/SKILL.md: has source but no vendor.json entry"
    ]
