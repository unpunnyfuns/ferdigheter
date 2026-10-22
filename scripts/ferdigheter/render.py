"""Build index.json content and the generated CATALOG.md table."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .model import Skill
from .skills import load_all

OPTIONAL_FIELDS = ("license", "source", "tags", "metadata")
START_MARKER = "<!-- index:start -->"
END_MARKER = "<!-- index:end -->"
CATALOG_FILE = "CATALOG.md"
INDEX_FILE = "index.json"


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


def splice_catalog(text: str, table: str) -> str:
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
    catalog_path = root / CATALOG_FILE
    try:
        catalog = splice_catalog(
            catalog_path.read_text(encoding="utf-8"), render_sections(index["skills"])
        )
    except (OSError, ValueError) as exc:
        return {}, [f"{CATALOG_FILE}: {exc}"]
    index_text = json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    return {root / INDEX_FILE: index_text, catalog_path: catalog}, []


def _existing_generated(root: Path) -> date:
    path = root / INDEX_FILE
    if path.is_file():
        try:
            return date.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["generated"])
        except (ValueError, KeyError, TypeError):
            pass
    return date.today()
