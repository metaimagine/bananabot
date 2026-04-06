from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bananabot import AgentLoop


@pytest.mark.asyncio
async def test_load_builtin_skills_registers_example_skill() -> None:
    loop = AgentLoop()

    await loop.load_builtin_skills()

    assert [skill.name for skill in loop.list_skills()] == ["example"]
    result = await loop.process("example", target="care")
    assert result == {"result": "hello, care"}


@pytest.mark.asyncio
async def test_load_skills_from_dir_discovers_local_skill(tmp_path: Path) -> None:
    skill_file = tmp_path / "temp_skill.py"
    skill_file.write_text(
        textwrap.dedent(
            """
            from bananabot import Skill

            class TempSkill(Skill):
                name = "temp"
                description = "temporary"

                async def execute(self, **kwargs):
                    return {"ok": kwargs.get("value", "missing")}
            """
        ),
        encoding="utf-8",
    )
    loop = AgentLoop()

    await loop.load_skills_from_dir(tmp_path)

    assert [skill.name for skill in loop.list_skills()] == ["temp"]
    assert await loop.process("temp", value="42") == {"ok": "42"}
