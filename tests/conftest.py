import json
import subprocess
from pathlib import Path

from ferdigheter.cli import main

VALID = "name: foo\ndescription: Does foo.\n"
CATALOG = "# Catalog\n\n<!-- index:start -->\n<!-- index:end -->\n"
UPSTREAM_V1 = (
    "---\nname: foo\ndescription: Upstream v1.\n"
    "license: Complete terms in LICENSE.txt\n---\n\n# Foo v1\n"
)


def make_skill(
    root: Path,
    name: str,
    frontmatter: str = VALID,
    body: str = "# Foo\n",
    category: str = "misc",
) -> Path:
    if frontmatter == VALID:
        frontmatter = frontmatter.replace("foo", name)
    skill_dir = root / "skills" / category / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return skill_dir


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "CATALOG.md").write_text(CATALOG, encoding="utf-8")
    make_skill(tmp_path, "foo", "name: foo\ndescription: Does foo.\ntags: [x]\n")
    return tmp_path


def write_manifest_file(root: Path, manifest) -> None:
    (root / "vendor.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")


def commit_all(path: Path, message: str) -> str:
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)
    return git(path, "rev-parse", "HEAD")


def make_upstream(
    tmp_path: Path, text: str = UPSTREAM_V1, extra: dict[str, str] | None = None
) -> tuple[str, str]:
    repo = tmp_path / "upstream"
    init_repo(repo)
    skill = repo / "skills" / "foo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(text, encoding="utf-8")
    for name, content in (extra or {}).items():
        (skill / name).write_text(content, encoding="utf-8")
    sha = commit_all(repo, "v1")
    return f"file://{repo}", sha


def make_vendored_repo(tmp_path: Path) -> tuple[Path, str, str]:
    url, sha = make_upstream(tmp_path)
    root = tmp_path / "reg"
    init_repo(root)
    (root / "CATALOG.md").write_text(CATALOG, encoding="utf-8")
    make_skill(
        root, "foo", "name: foo\ndescription: Old.\nlicense: MIT\nsource: https://x\ntags: [a]\n"
    )
    write_manifest_file(root, {"misc/foo": {"repo": url, "path": "skills/foo", "ref": "main"}})
    main(["--root", str(root), "build"])
    commit_all(root, "vendored")
    return root, url, sha


def make_bare_registry(tmp_path: Path) -> Path:
    root = tmp_path / "reg"
    init_repo(root)
    (root / "CATALOG.md").write_text(CATALOG, encoding="utf-8")
    commit_all(root, "init")
    return root
