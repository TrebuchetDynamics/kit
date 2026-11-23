#!/usr/bin/env python3
"""Install Kit's two planning commands for the current OpenCode user."""

import json
import os
from pathlib import Path


def main():
    adapters = Path(__file__).resolve().parents[1]
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    # XDG base directories must be absolute; never install into the current project.
    if not config_home.is_absolute():
        raise SystemExit("XDG_CONFIG_HOME must be an absolute path (or unset).")
    commands_dir = config_home / "opencode" / "commands"
    workflows = {
        "plan-with-me": "Clarify scope with questions and plan with Kit.",
        "plan-for-me": "Investigate and plan with Kit without an interview.",
    }
    pending = {}
    for name, description in workflows.items():
        adapter = adapters / "skills" / name / "SKILL.md"
        if not adapter.is_file():
            raise SystemExit(f"Missing Kit workflow: {adapter}")
        command = commands_dir / f"{name}.md"
        path = json.dumps(str(adapter), ensure_ascii=False)
        template = (
            f"---\ndescription: {description}\n---\n\n"
            f"Run Kit's {name} workflow in the current project. Read the adapter at {path} "
            "completely and follow it, resolving references relative to the files that contain them. "
            "Use the current conversation and any text following this template as the user's request.\n"
        )
        if command.is_symlink() or command.exists():
            if not command.is_symlink() and command.is_file() and command.read_bytes() == template.encode():
                continue
            raise SystemExit(f"Existing OpenCode command differs: {command}. Move it aside before installing.")
        pending[command] = template

    commands_dir.mkdir(parents=True, exist_ok=True)
    for command, template in pending.items():
        with command.open("x", encoding="utf-8") as stream:
            stream.write(template)
    print(f"Kit planning commands are installed in {commands_dir}")


if __name__ == "__main__":
    main()
