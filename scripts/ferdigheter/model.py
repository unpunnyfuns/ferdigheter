"""Shared types, patterns and limits used across the registry modules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*/[a-z0-9]+(-[a-z0-9]+)*$")
SPDX_RE = re.compile(r"^[A-Za-z0-9.+-]+$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
SKILL_FILE = "SKILL.md"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent


class Skill(NamedTuple):
    category: str
    dirname: str
    data: dict


class FrontmatterError(ValueError):
    """Raised when SKILL.md has missing or malformed frontmatter."""


def skill_label(skill: Skill) -> str:
    return f"skills/{skill.category}/{skill.dirname}/{SKILL_FILE}"
