"""Command implementations behind the validate, build, sync and add subcommands."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from .manifest import VENDOR_FILE, _sync_entry_problems, load_manifest, write_manifest
from .model import SKILL_FILE, FrontmatterError
from .render import _existing_generated, render_outputs
from .skills import discover
from .vendor import (
    dirty_keys,
    has_license_file,
    license_text,
    parse_tags,
    remote_commit,
    set_registry_fields,
    sync_skill,
)


def _report(problems: list[str]) -> int:
    for problem in problems:
        print(problem)
    return 1 if problems else 0


def _short(commit: str | None) -> str:
    return commit[:7] if commit else "none"


def _first_line(text: str | None) -> str:
    lines = (text or "").strip().splitlines()
    return lines[0] if lines else "unknown error"


def run_build(root: Path, check: bool) -> int:
    today = _existing_generated(root) if check else date.today()
    outputs, problems = render_outputs(root, today)
    if problems:
        return _report(problems)
    if check:
        stale = [
            path
            for path, content in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        for path in stale:
            print(f"{path.relative_to(root)} is out of date")
        return 1 if stale else 0
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    return 0


def _sync_check(manifest: dict, keys: list[str]) -> int:
    stale: list[str] = []
    for key in keys:
        entry = manifest[key]
        try:
            latest = remote_commit(entry["repo"], entry["ref"])
        except subprocess.CalledProcessError as exc:
            return _report([f"{key}: git ls-remote failed: {_first_line(exc.stderr)}"])
        if latest != entry.get("commit"):
            stale.append(f"{key}: {_short(entry.get('commit'))} -> {_short(latest)}")
    return _report(stale)


def run_sync(root: Path, keys: list[str], check: bool) -> int:
    manifest, problems = load_manifest(root)
    if problems:
        return _report(problems)
    selected = keys or sorted(manifest)
    unknown = [key for key in selected if key not in manifest]
    if unknown:
        return _report([f"{VENDOR_FILE}: unknown key {key!r}" for key in unknown])
    bad = [p for key in selected for p in _sync_entry_problems(key, manifest[key])]
    if bad:
        return _report(bad)
    if check:
        return _sync_check(manifest, selected)
    try:
        dirty = dirty_keys(root, selected)
    except subprocess.CalledProcessError as exc:
        return _report([f"git status failed: {_first_line(exc.stderr)}"])
    if dirty:
        return _report([f"skills/{key}: has uncommitted changes" for key in dirty])
    failures: list[str] = []
    synced = False
    for key in selected:
        entry = manifest[key]
        try:
            commit = sync_skill(root, key, entry)
        except subprocess.CalledProcessError as exc:
            failures.append(f"{key}: git {exc.cmd[1]} failed: {_first_line(exc.stderr)}")
            break
        except (FileNotFoundError, FrontmatterError) as exc:
            failures.append(f"{key}: {exc}")
            break
        print(f"{key}: {_short(entry.get('commit'))} -> {_short(commit)}")
        entry["commit"] = commit
        synced = True
    if synced:
        write_manifest(root, manifest)
    if failures:
        return _report(failures)
    return run_build(root, check=False)


def _name_in_other_category(root: Path, key: str) -> str | None:
    category, name = key.split("/")
    for skill_dir in discover(root):
        if skill_dir.name == name and skill_dir.parent.name != category:
            return skill_dir.parent.name
    return None


def run_add(
    root: Path,
    key: str,
    repo: str,
    path: str,
    ref: str,
    spdx: str,
    tags_text: str,
    copyright: str | None,
) -> int:
    entry = {"repo": repo, "path": path, "ref": ref}
    problems = _sync_entry_problems(key, entry)
    if problems:
        return _report(problems)
    manifest, problems = load_manifest(root)
    if problems:
        return _report(problems)
    if key in manifest:
        return _report([f"{VENDOR_FILE}: {key!r} already exists"])
    skill_dir = root / "skills" / key
    if skill_dir.exists():
        return _report([f"skills/{key}: already exists"])
    try:
        tags = parse_tags(tags_text)
    except ValueError as exc:
        return _report([str(exc)])
    if not spdx.strip():
        return _report(["license must be a non-empty string"])
    name = key.split("/")[1]
    other_category = _name_in_other_category(root, key)
    if other_category:
        return _report(
            [f"skills/{key}: name {name!r} already used in skills/{other_category}/{name}"]
        )
    try:
        commit = sync_skill(root, key, entry)
    except subprocess.CalledProcessError as exc:
        return _report([f"{key}: git {exc.cmd[1]} failed: {_first_line(exc.stderr)}"])
    except (FileNotFoundError, FrontmatterError) as exc:
        return _report([f"{key}: {exc}"])
    print(f"{key}: none -> {_short(commit)}")
    manifest[key] = {**entry, "commit": commit}
    write_manifest(root, manifest)
    fields = {"name": name, "license": spdx, "source": repo}
    if tags:
        fields["tags"] = tags
    set_registry_fields(skill_dir / SKILL_FILE, fields)
    if not has_license_file(skill_dir):
        _write_license(skill_dir, key, spdx, copyright)
    code = run_build(root, check=False)
    if code:
        print(
            f"skills/{key}: added but validation failed; clean up with: "
            f"rm -rf skills/{key} and remove the entry from vendor.json"
        )
    return code


def _write_license(skill_dir: Path, key: str, spdx: str, copyright: str | None) -> None:
    try:
        text = license_text(spdx, copyright)
    except ValueError as exc:
        if str(exc) != "copyright required":
            raise
        print(f"skills/{key}/LICENSE: not written, pass --copyright")
        return
    if text is None:
        print(f"skills/{key}/LICENSE: no template for {spdx}, add it manually")
        return
    (skill_dir / "LICENSE").write_text(text, encoding="utf-8")
    print(f"wrote skills/{key}/LICENSE")
