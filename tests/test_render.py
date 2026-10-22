from datetime import date

import pytest

from ferdigheter.model import Skill
from ferdigheter.render import build_index, render_sections, render_table, splice_catalog


def test_build_index_sorts_and_omits_optional():
    skills = [
        Skill("misc", "zeta", {"name": "zeta", "description": " Z \n"}),
        Skill(
            "misc",
            "alpha",
            {
                "name": "alpha",
                "description": "A",
                "license": "MIT",
                "source": "https://x",
                "tags": ["t"],
                "metadata": {"v": "1"},
                "ignored": True,
            },
        ),
    ]
    index = build_index(skills, date(2026, 10, 22))
    assert index == {
        "generated": "2026-10-22",
        "skills": [
            {
                "name": "alpha",
                "category": "misc",
                "description": "A",
                "path": "skills/misc/alpha",
                "license": "MIT",
                "source": "https://x",
                "tags": ["t"],
                "metadata": {"v": "1"},
            },
            {
                "name": "zeta",
                "category": "misc",
                "description": "Z",
                "path": "skills/misc/zeta",
            },
        ],
    }


def test_render_table():
    entries = [
        {
            "name": "a",
            "category": "c",
            "description": "Has | pipe\nand newline",
            "path": "skills/c/a",
            "tags": ["x", "y"],
        },
        {"name": "b", "category": "c", "description": "Plain", "path": "skills/c/b"},
    ]
    assert render_table(entries) == (
        "| Skill | Description | Tags |\n"
        "|---|---|---|\n"
        "| [a](skills/c/a/) | Has \\| pipe and newline | x, y |\n"
        "| [b](skills/c/b/) | Plain |  |"
    )


def test_render_sections_groups_by_category():
    entries = [
        {"name": "a", "category": "web", "description": "A", "path": "skills/web/a"},
        {"name": "b", "category": "process", "description": "B", "path": "skills/process/b"},
        {"name": "c", "category": "web", "description": "C", "path": "skills/web/c"},
    ]
    assert render_sections(entries) == (
        "### process\n\n"
        "| Skill | Description | Tags |\n|---|---|---|\n"
        "| [b](skills/process/b/) | B |  |\n"
        "\n"
        "### web\n\n"
        "| Skill | Description | Tags |\n|---|---|---|\n"
        "| [a](skills/web/a/) | A |  |\n"
        "| [c](skills/web/c/) | C |  |"
    )


def test_render_sections_empty():
    assert render_sections([]) == ""


def test_splice_catalog_replaces_between_markers():
    text = "# T\n\nintro\n\n<!-- index:start -->\nold\n<!-- index:end -->\n\nfooter\n"
    out = splice_catalog(text, "TABLE")
    assert out == "# T\n\nintro\n\n<!-- index:start -->\nTABLE\n<!-- index:end -->\n\nfooter\n"


def test_splice_catalog_missing_markers():
    with pytest.raises(ValueError, match="markers"):
        splice_catalog("# T\n", "TABLE")
