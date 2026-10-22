#!/usr/bin/env python3
"""Validate skills under skills/ and build index.json plus the README table."""

from __future__ import annotations

import yaml


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
