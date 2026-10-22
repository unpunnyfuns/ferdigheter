"""Parse, dump and merge SKILL.md frontmatter."""

from __future__ import annotations

import yaml

from .model import FrontmatterError

REGISTRY_FIELDS = ("license", "source", "tags")


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


def dump_frontmatter(data: dict, body: str) -> str:
    raw = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=10_000)
    return f"---\n{raw}---\n{body}"


def registry_fields(data: dict) -> dict:
    return {key: data[key] for key in REGISTRY_FIELDS if key in data}


def kept_fields(data: dict) -> dict:
    kept = registry_fields(data)
    if "name" in data:
        kept["name"] = data["name"]
    return kept


def _rstrip_strings(value: object) -> object:
    if isinstance(value, str):
        return value.rstrip()
    if isinstance(value, list):
        return [_rstrip_strings(v) for v in value]
    if isinstance(value, dict):
        return {k: _rstrip_strings(v) for k, v in value.items()}
    return value


def merge_frontmatter(upstream_text: str, overrides: dict) -> str:
    data, body = parse_frontmatter(upstream_text)
    data = _rstrip_strings(data)
    if "name" in overrides:
        data["name"] = overrides["name"]
    upstream_only = {key: value for key, value in data.items() if key not in REGISTRY_FIELDS}
    return dump_frontmatter({**upstream_only, **registry_fields(overrides)}, body)
