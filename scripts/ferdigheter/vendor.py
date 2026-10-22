"""Clone upstream repos, replace vendored skill folders and write LICENSE files."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .frontmatter import kept_fields, merge_frontmatter, parse_frontmatter
from .model import NAME_RE, SCRIPTS_DIR, SKILL_FILE, SPDX_RE

LICENSE_DIR = SCRIPTS_DIR / "licenses"


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


def replace_skill(skill_dir: Path, upstream_dir: Path) -> None:
    old_skill_md = skill_dir / SKILL_FILE
    overrides = {}
    if old_skill_md.is_file():
        overrides = kept_fields(parse_frontmatter(old_skill_md.read_text(encoding="utf-8"))[0])
    merged = merge_frontmatter((upstream_dir / SKILL_FILE).read_text(encoding="utf-8"), overrides)
    old_license = skill_dir / "LICENSE"
    kept_license = None
    if old_license.is_file() and not (upstream_dir / "LICENSE").exists():
        kept_license = old_license.read_bytes()
    shutil.rmtree(skill_dir, ignore_errors=True)
    shutil.copytree(upstream_dir, skill_dir)
    (skill_dir / SKILL_FILE).write_text(merged, encoding="utf-8")
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
        if not (upstream_dir / SKILL_FILE).is_file():
            raise FileNotFoundError(f"path {entry['path']!r} has no {SKILL_FILE}")
        replace_skill(root / "skills" / key, upstream_dir)
    return commit


def dirty_keys(root: Path, keys: list[str]) -> list[str]:
    return [
        key
        for key in keys
        if _git("status", "--porcelain", "-uall", "--", f"skills/{key}", cwd=root)
    ]


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
