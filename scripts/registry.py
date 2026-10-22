#!/usr/bin/env python3
"""Validate skills under skills/ and build index.json plus the README table."""

from __future__ import annotations

import argparse
import json
import re
import sys
import yaml
from datetime import date
from pathlib import Path
from typing import NamedTuple


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
OPTIONAL_FIELDS = ("license", "source", "tags", "metadata")
START_MARKER = "<!-- index:start -->"
END_MARKER = "<!-- index:end -->"


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
    for stray in stray_skills(root):
        problems.append(f"skills/{stray.name}/SKILL.md: skills must live under a category folder")
    for skill_dir in discover(root):
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
        readme = splice_readme(readme_path.read_text(encoding="utf-8"), render_sections(index["skills"]))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check every skill, print problems")
    build = sub.add_parser("build", help="validate, then write index.json and README table")
    build.add_argument("--check", action="store_true", help="fail if outputs are out of date")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "validate":
        _, problems = load_all(root)
        return _report(problems)

    today = _existing_generated(root) if args.check else date.today()
    outputs, problems = render_outputs(root, today)
    if problems:
        return _report(problems)

    if args.check:
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


if __name__ == "__main__":
    sys.exit(main())
