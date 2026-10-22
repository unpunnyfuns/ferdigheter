"""Argument parsing and dispatch for the registry command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from .commands import _report, run_add, run_build, run_sync
from .model import REPO_ROOT
from .skills import load_all

DESCRIPTION = "Validate skills under skills/ and build index.json plus the CATALOG.md table."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check every skill, print problems")
    build = sub.add_parser("build", help="validate, then write index.json and CATALOG.md table")
    build.add_argument("--check", action="store_true", help="fail if outputs are out of date")
    sync = sub.add_parser("sync", help="pull vendored skills from upstream per vendor.json")
    sync.add_argument("keys", nargs="*", help="<category>/<name> entries to sync; default all")
    sync.add_argument(
        "--check", action="store_true", help="only report entries with newer upstream commits"
    )
    add = sub.add_parser("add", help="vendor a third-party skill in one step")
    add.add_argument("key", help="<category>/<name>")
    add.add_argument("--repo", required=True, help="git URL of the upstream repo")
    add.add_argument("--path", required=True, help="skill folder inside the upstream repo")
    add.add_argument("--ref", default="main", help="branch or tag, default main")
    add.add_argument("--license", required=True, help="SPDX id, e.g. MIT or Apache-2.0")
    add.add_argument("--tags", default="", help="comma-separated kebab-case tags")
    add.add_argument("--copyright", help='copyright line for generated LICENSE, e.g. "2025 Vendor"')
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "validate":
        _, problems = load_all(root)
        return _report(problems)
    if args.command == "sync":
        return run_sync(root, args.keys, args.check)
    if args.command == "add":
        return run_add(
            root, args.key, args.repo, args.path, args.ref, args.license, args.tags, args.copyright
        )
    return run_build(root, args.check)
