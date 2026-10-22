import json
from datetime import date

from conftest import make_repo, make_skill
from ferdigheter.cli import main


def test_cli_validate(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "validate"]) == 0
    assert capsys.readouterr().out == ""

    make_skill(tmp_path, "bad", "name: nope\ndescription: x\n")
    assert main(["--root", str(tmp_path), "validate"]) == 1
    assert (
        capsys.readouterr().out
        == "skills/misc/bad/SKILL.md: name 'nope' does not match folder 'bad'\n"
    )


def test_cli_build_writes_outputs(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "build"]) == 0
    assert capsys.readouterr().out == ""
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["generated"] == date.today().isoformat()
    assert index["skills"][0]["name"] == "foo"
    assert (tmp_path / "index.json").read_text(encoding="utf-8").endswith("}\n")
    catalog = (tmp_path / "CATALOG.md").read_text(encoding="utf-8")
    assert "### misc\n\n| Skill |" in catalog
    assert "| [foo](skills/misc/foo/) | Does foo. | x |" in catalog
    assert index["skills"][0]["category"] == "misc"


def test_cli_build_refuses_on_problems(tmp_path):
    make_repo(tmp_path)
    make_skill(tmp_path, "bad", "name: nope\ndescription: x\n")
    assert main(["--root", str(tmp_path), "build"]) == 1
    assert not (tmp_path / "index.json").exists()


def test_cli_build_missing_markers(tmp_path, capsys):
    make_repo(tmp_path)
    (tmp_path / "CATALOG.md").write_text("# no markers\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "build"]) == 1
    assert capsys.readouterr().out == "CATALOG.md: missing index markers\n"


def test_cli_build_check(tmp_path, capsys):
    make_repo(tmp_path)
    assert main(["--root", str(tmp_path), "build", "--check"]) == 1
    assert capsys.readouterr().out == "index.json is out of date\nCATALOG.md is out of date\n"
    assert not (tmp_path / "index.json").exists()

    main(["--root", str(tmp_path), "build"])
    assert main(["--root", str(tmp_path), "build", "--check"]) == 0

    make_skill(tmp_path, "bar")
    assert main(["--root", str(tmp_path), "build", "--check"]) == 1

    main(["--root", str(tmp_path), "build"])
    index_path = tmp_path / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["generated"] = "2000-01-01"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "build", "--check"]) == 0
