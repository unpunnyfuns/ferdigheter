#!/usr/bin/env python3
"""Validate skills under skills/ and build index.json plus the README table."""

from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import NamedTuple


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024


class Skill(NamedTuple):
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
    return Skill(skill_dir.name, data)


def discover(root: Path) -> list[Path]:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("_"))


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

    if "metadata" in data and not isinstance(data["metadata"], dict):
        problems.append("metadata must be a mapping")

    return problems


def load_all(root: Path) -> tuple[list[Skill], list[str]]:
    skills: list[Skill] = []
    problems: list[str] = []
    for skill_dir in discover(root):
        label = f"skills/{skill_dir.name}/SKILL.md"
        try:
            skill = load_skill(skill_dir)
        except FrontmatterError as exc:
            problems.append(f"{label}: {exc}")
            continue
        problems.extend(f"{label}: {p}" for p in validate_skill(skill))
        skills.append(skill)
    return skills, problems
