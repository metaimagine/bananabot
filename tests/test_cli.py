from __future__ import annotations

import json

from bananabot.cli import main


def test_cli_lists_builtin_skills(capsys) -> None:
    exit_code = main(["list-skills"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "example: Return a small structured result for smoke testing" in captured.out


def test_cli_runs_skill_with_args(capsys) -> None:
    exit_code = main(["run", "example", "--arg", "target=care"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == {"result": "hello, care"}
