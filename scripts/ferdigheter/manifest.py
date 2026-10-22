"""Read, write and validate the vendor.json manifest."""

from __future__ import annotations

import json
from pathlib import Path

from .model import KEY_RE, Skill, skill_label

VENDOR_FILE = "vendor.json"


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
