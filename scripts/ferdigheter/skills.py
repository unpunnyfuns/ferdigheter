"""Discover skill folders and validate their frontmatter."""

from __future__ import annotations

import json
from pathlib import Path

from .frontmatter import parse_frontmatter
from .manifest import load_manifest, validate_manifest
from .model import (
    MAX_DESCRIPTION,
    MAX_NAME,
    NAME_RE,
    SKILL_FILE,
    FrontmatterError,
    Skill,
    skill_label,
)


def load_skill(skill_dir: Path) -> Skill:
    path = skill_dir / SKILL_FILE
    if not path.is_file():
        raise FrontmatterError(f"{SKILL_FILE} not found")
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
    return [d for d in _visible_dirs(root / "skills") if (d / SKILL_FILE).is_file()]


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
        if not isinstance(source, str) or not source.strip():
            problems.append("source must be a non-empty string")

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


def load_all(root: Path) -> tuple[list[Skill], list[str]]:
    skills: list[Skill] = []
    problems: list[str] = []
    strays = stray_skills(root)
    for stray in strays:
        problems.append(
            f"skills/{stray.name}/{SKILL_FILE}: skills must live under a category folder"
        )
    for skill_dir in discover(root):
        if skill_dir.parent in strays:
            continue
        label = f"skills/{skill_dir.parent.name}/{skill_dir.name}/{SKILL_FILE}"
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
