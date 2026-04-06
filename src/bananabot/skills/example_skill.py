from __future__ import annotations

from bananabot import Skill


class ExampleSkill(Skill):
    name = "example"
    description = "Return a small structured result for smoke testing"

    async def execute(self, **kwargs: str) -> dict[str, str]:
        target = kwargs.get("target", "world")
        return {"result": f"hello, {target}"}
