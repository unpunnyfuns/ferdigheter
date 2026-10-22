#!/usr/bin/env python3
"""Validate skills under skills/ and build index.json plus the README table."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import yaml

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
OPTIONAL_FIELDS = ("license", "source", "tags", "metadata")
REGISTRY_FIELDS = ("license", "source", "tags")
START_MARKER = "<!-- index:start -->"
END_MARKER = "<!-- index:end -->"
VENDOR_FILE = "vendor.json"
KEY_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*/[a-z0-9]+(-[a-z0-9]+)*$")
SPDX_RE = re.compile(r"^[A-Za-z0-9.+-]+$")
LICENSE_DIR = Path(__file__).resolve().parent / "licenses"


class Skill(NamedTuple):
    category: str
    dirname: str
    data: dict


class FrontmatterError(ValueError):
    """Raised when SKILL.md has missing or malformed frontmatter."""


def parse_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.split("\n")
    if lines[0] != "---":
        raise FrontmatterError("missing frontmatter")
    for i in range(1, len(lines)):
        if lines[i] == "---":
            raw = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            break
    else:
        raise FrontmatterError("unterminated frontmatter")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid yaml: {exc}") from exc
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return data, body


def load_skill(skill_dir: Path) -> Skill:
    path = skill_dir / "SKILL.md"
    if not path.is_file():
        raise FrontmatterError("SKILL.md not found")
    data, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Skill(skill_dir.parent.name, skill_dir.name, data)


def _visible_dirs(parent: Path) -> list[Path]:
    if not parent.is_dir():
        return []
    return sorted(p for p in parent.iterdir() if p.is_dir() and not p.name.startswith("_"))


def discover(root: Path) -> list[Path]:
    return [
        skill_dir
        for category_dir in _visible_dirs(root / "skills")
        for skill_dir in _visible_dirs(category_dir)
    ]


def stray_skills(root: Path) -> list[Path]:
    return [d for d in _visible_dirs(root / "skills") if (d / "SKILL.md").is_file()]


def skill_label(skill: Skill) -> str:
    return f"skills/{skill.category}/{skill.dirname}/SKILL.md"


def validate_skill(skill: Skill) -> list[str]:
    data = skill.data
    problems: list[str] = []

    name = data.get("name")
    if not isinstance(name, str) or not name:
        problems.append("name is required")
    else:
        if not NAME_RE.match(name):
            problems.append(f"name {name!r} is not kebab-case")
        if len(name) > MAX_NAME:
            problems.append(f"name is longer than {MAX_NAME} chars")
        if name != skill.dirname:
            problems.append(f"name {name!r} does not match folder {skill.dirname!r}")

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append("description is required")
    elif len(description.strip()) > MAX_DESCRIPTION:
        problems.append(f"description is longer than {MAX_DESCRIPTION} chars")
    elif "<!--" in description:
        problems.append("description must not contain HTML comments")

    if "license" in data:
        license_ = data["license"]
        if not isinstance(license_, str) or not license_.strip():
            problems.append("license must be a non-empty string")

    if "source" in data:
        source = data["source"]
        if not isinstance(source, str) or not source.startswith("https://"):
            problems.append("source must be an https:// URL")

    if "tags" in data:
        tags = data["tags"]
        valid_tags = isinstance(tags, list) and all(
            isinstance(t, str) and NAME_RE.match(t) for t in tags
        )
        if not valid_tags:
            problems.append("tags must be a list of kebab-case strings")

    if "metadata" in data:
        if not isinstance(data["metadata"], dict):
            problems.append("metadata must be a mapping")
        else:
            try:
                json.dumps(data["metadata"])
            except TypeError:
                problems.append("metadata must be JSON-serializable")

    return problems


def load_all(root: Path) -> tuple[list[Skill], list[str]]:
    skills: list[Skill] = []
    problems: list[str] = []
    strays = stray_skills(root)
    for stray in strays:
        problems.append(f"skills/{stray.name}/SKILL.md: skills must live under a category folder")
    for skill_dir in discover(root):
        if skill_dir.parent in strays:
            continue
        label = f"skills/{skill_dir.parent.name}/{skill_dir.name}/SKILL.md"
        try:
            skill = load_skill(skill_dir)
        except FrontmatterError as exc:
            problems.append(f"{label}: {exc}")
            continue
        if not NAME_RE.match(skill.category):
            problems.append(f"{label}: category {skill.category!r} is not kebab-case")
        problems.extend(f"{label}: {p}" for p in validate_skill(skill))
        skills.append(skill)
    problems.extend(_duplicate_problems(skills))
    manifest, manifest_problems = load_manifest(root)
    problems.extend(manifest_problems)
    problems.extend(validate_manifest(root, manifest, skills))
    return skills, problems


def _duplicate_problems(skills: list[Skill]) -> list[str]:
    by_name: dict[str, list[Skill]] = {}
    for skill in skills:
        by_name.setdefault(skill.dirname, []).append(skill)
    problems: list[str] = []
    for skill in skills:
        others = [s for s in by_name[skill.dirname] if s is not skill]
        for other in others:
            problems.append(
                f"{skill_label(skill)}: duplicate skill name {skill.dirname!r}, "
                f"also in skills/{other.category}/{other.dirname}"
            )
    return problems


def load_manifest(root: Path) -> tuple[dict, list[str]]:
    path = root / VENDOR_FILE
    if not path.is_file():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"{VENDOR_FILE}: invalid json: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{VENDOR_FILE}: must be a JSON object"]
    return data, []


def write_manifest(root: Path, manifest: dict) -> None:
    ordered = {key: manifest[key] for key in sorted(manifest)}
    text = json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"
    (root / VENDOR_FILE).write_text(text, encoding="utf-8")


def _entry_complete(entry: object) -> bool:
    return isinstance(entry, dict) and all(
        isinstance(entry.get(field), str) and entry[field] for field in ("repo", "path", "ref")
    )


def validate_manifest(root: Path, manifest: dict, skills: list[Skill]) -> list[str]:
    problems: list[str] = []
    for key, entry in manifest.items():
        if not KEY_RE.match(key):
            problems.append(f"{VENDOR_FILE}: key {key!r} is not <category>/<name>")
            continue
        if not (root / "skills" / key).is_dir():
            problems.append(f"{VENDOR_FILE}: {key!r} has no skill folder")
        if not _entry_complete(entry):
            problems.append(f"{VENDOR_FILE}: {key!r} needs repo, path and ref")
    for skill in skills:
        if "source" in skill.data and f"{skill.category}/{skill.dirname}" not in manifest:
            problems.append(f"{skill_label(skill)}: has source but no vendor.json entry")
    return problems


def dump_frontmatter(data: dict, body: str) -> str:
    raw = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=10_000)
    return f"---\n{raw}---\n{body}"


def registry_fields(data: dict) -> dict:
    return {key: data[key] for key in REGISTRY_FIELDS if key in data}


def merge_frontmatter(upstream_text: str, overrides: dict) -> str:
    data, body = parse_frontmatter(upstream_text)
    if "name" in overrides:
        data["name"] = overrides["name"]
    upstream_only = {key: value for key, value in data.items() if key not in REGISTRY_FIELDS}
    return dump_frontmatter({**upstream_only, **registry_fields(overrides)}, body)


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def fetch_upstream(repo: str, ref: str, dest: Path) -> str:
    _git("clone", "--quiet", "--depth", "1", "--branch", ref, "--", repo, str(dest))
    return _git("rev-parse", "HEAD", cwd=dest)


def remote_commit(repo: str, ref: str) -> str:
    output = _git(
        "ls-remote",
        "--",
        repo,
        f"refs/heads/{ref}",
        f"refs/tags/{ref}",
        f"refs/tags/{ref}^{{}}",
    )
    if not output:
        raise subprocess.CalledProcessError(
            1, ["git", "ls-remote"], stderr=f"ref {ref!r} not found in {repo}"
        )
    refs = [line.split(maxsplit=1) for line in output.splitlines() if line.strip()]
    peeled = [sha for sha, name in refs if name.endswith("^{}")]
    if peeled:
        return peeled[0]
    branches = [sha for sha, name in refs if name.startswith("refs/heads/")]
    if branches:
        return branches[0]
    return refs[0][0]


def kept_fields(data: dict) -> dict:
    kept = registry_fields(data)
    if "name" in data:
        kept["name"] = data["name"]
    return kept


def replace_skill(skill_dir: Path, upstream_dir: Path) -> None:
    old_skill_md = skill_dir / "SKILL.md"
    overrides = {}
    if old_skill_md.is_file():
        overrides = kept_fields(parse_frontmatter(old_skill_md.read_text(encoding="utf-8"))[0])
    merged = merge_frontmatter((upstream_dir / "SKILL.md").read_text(encoding="utf-8"), overrides)
    old_license = skill_dir / "LICENSE"
    kept_license = None
    if old_license.is_file() and not (upstream_dir / "LICENSE").exists():
        kept_license = old_license.read_bytes()
    shutil.rmtree(skill_dir, ignore_errors=True)
    shutil.copytree(upstream_dir, skill_dir)
    (skill_dir / "SKILL.md").write_text(merged, encoding="utf-8")
    if kept_license is not None:
        (skill_dir / "LICENSE").write_bytes(kept_license)


def sync_skill(root: Path, key: str, entry: dict) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "upstream"
        commit = fetch_upstream(entry["repo"], entry["ref"], clone)
        upstream_dir = clone / entry["path"]
        if not upstream_dir.is_dir():
            raise FileNotFoundError(
                f"path {entry['path']!r} not found in {entry['repo']}@{entry['ref']}"
            )
        if not (upstream_dir / "SKILL.md").is_file():
            raise FileNotFoundError(f"path {entry['path']!r} has no SKILL.md")
        replace_skill(root / "skills" / key, upstream_dir)
    return commit


def parse_tags(text: str) -> list[str]:
    tags = [t.strip() for t in text.split(",") if t.strip()]
    if not all(NAME_RE.match(t) for t in tags):
        raise ValueError("tags must be kebab-case, comma-separated")
    return tags


def license_text(spdx: str, copyright: str | None) -> str | None:
    if not SPDX_RE.match(spdx):
        return None
    template = LICENSE_DIR / f"{spdx}.txt"
    if not template.is_file():
        return None
    text = template.read_text(encoding="utf-8")
    if "{copyright}" in text:
        if copyright is None:
            raise ValueError("copyright required")
        text = text.replace("{copyright}", copyright)
    return text


def has_license_file(skill_dir: Path) -> bool:
    return any(p.is_file() and p.name.upper().startswith("LICENSE") for p in skill_dir.iterdir())


def set_registry_fields(skill_md: Path, fields: dict) -> None:
    merged = merge_frontmatter(skill_md.read_text(encoding="utf-8"), fields)
    skill_md.write_text(merged, encoding="utf-8")


def index_entry(skill: Skill) -> dict:
    data = skill.data
    entry = {
        "name": data["name"],
        "category": skill.category,
        "description": data["description"].strip(),
        "path": f"skills/{skill.category}/{skill.dirname}",
    }
    for key in OPTIONAL_FIELDS:
        if key in data:
            entry[key] = data[key]
    return entry


def build_index(skills: list[Skill], today: date) -> dict:
    entries = sorted((index_entry(s) for s in skills), key=lambda e: e["name"])
    return {"generated": today.isoformat(), "skills": entries}


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def render_table(entries: list[dict]) -> str:
    lines = ["| Skill | Description | Tags |", "|---|---|---|"]
    for entry in entries:
        tags = ", ".join(entry.get("tags", []))
        lines.append(
            f"| [{entry['name']}]({entry['path']}/) | {_cell(entry['description'])} | {tags} |"
        )
    return "\n".join(lines)


def render_sections(entries: list[dict]) -> str:
    categories = sorted({e["category"] for e in entries})
    sections = [
        f"### {category}\n\n" + render_table([e for e in entries if e["category"] == category])
        for category in categories
    ]
    return "\n\n".join(sections)


def splice_readme(text: str, table: str) -> str:
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError("missing index markers")
    head = text[: start + len(START_MARKER)]
    return f"{head}\n{table}\n{text[end:]}"


def render_outputs(root: Path, today: date) -> tuple[dict[Path, str], list[str]]:
    skills, problems = load_all(root)
    if problems:
        return {}, problems
    index = build_index(skills, today)
    readme_path = root / "README.md"
    try:
        readme = splice_readme(
            readme_path.read_text(encoding="utf-8"), render_sections(index["skills"])
        )
    except (OSError, ValueError) as exc:
        return {}, [f"README.md: {exc}"]
    index_text = json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    return {root / "index.json": index_text, readme_path: readme}, []


def _existing_generated(root: Path) -> date:
    path = root / "index.json"
    if path.is_file():
        try:
            return date.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["generated"])
        except (ValueError, KeyError, TypeError):
            pass
    return date.today()


def _report(problems: list[str]) -> int:
    for problem in problems:
        print(problem)
    return 1 if problems else 0


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


def _short(commit: str | None) -> str:
    return commit[:7] if commit else "none"


def _first_line(text: str | None) -> str:
    lines = (text or "").strip().splitlines()
    return lines[0] if lines else "unknown error"


def dirty_keys(root: Path, keys: list[str]) -> list[str]:
    return [
        key
        for key in keys
        if _git("status", "--porcelain", "-uall", "--", f"skills/{key}", cwd=root)
    ]


def _sync_entry_problems(key: str, entry: object) -> list[str]:
    if not KEY_RE.match(key):
        return [f"{VENDOR_FILE}: key {key!r} is not <category>/<name>"]
    if not _entry_complete(entry):
        return [f"{VENDOR_FILE}: {key!r} needs repo, path and ref"]
    path = PurePosixPath(entry["path"])
    if path.is_absolute() or ".." in path.parts:
        return [f"{VENDOR_FILE}: {key!r} path must be a relative path inside the repo"]
    return []


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check every skill, print problems")
    build = sub.add_parser("build", help="validate, then write index.json and README table")
    build.add_argument("--check", action="store_true", help="fail if outputs are out of date")
    sync = sub.add_parser("sync", help="pull vendored skills from upstream per vendor.json")
    sync.add_argument("keys", nargs="*", help="<category>/<name> entries to sync; default all")
    sync.add_argument(
        "--check", action="store_true", help="only report entries with newer upstream commits"
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "validate":
        _, problems = load_all(root)
        return _report(problems)
    if args.command == "sync":
        return run_sync(root, args.keys, args.check)
    return run_build(root, args.check)


if __name__ == "__main__":
    sys.exit(main())
