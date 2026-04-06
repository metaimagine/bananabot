# BananaBot

Minimal agent loop with pluggable skills.

## Quick Start

```bash
pip install -e ".[dev]"
bananabot list-skills
bananabot run example --arg target=care
```

## Layout

```text
bananabot/
├── src/bananabot/
│   ├── __init__.py
│   ├── cli.py
│   ├── core.py
│   └── skills/
│       ├── __init__.py
│       └── example_skill.py
└── tests/
```

## Current Scope

- Minimal `AgentLoop` that registers and runs skills.
- Dynamic skill loading from a directory.
- Small CLI for listing and running skills.
- Focused pytest coverage for the core flow.

This is intentionally thin. It is a base to keep iterating from, not a full nanobot clone.
