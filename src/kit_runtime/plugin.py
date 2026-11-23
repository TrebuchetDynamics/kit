"""Discover bundled skills and expose them through Hermes' command API."""

from functools import partial
import logging
from pathlib import Path
import re


SKILLS_DIR = _KIT_LAYOUT.root / "skills"
logger = logging.getLogger(__name__)


_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")


def _discover_skills():
    """Validate the complete command set before registering anything."""
    root = SKILLS_DIR.resolve()
    skills = []
    commands = set()
    for folder in sorted(root.iterdir()):
        path = folder / "SKILL.md"
        if folder.name in {"repo-docs", "repo-interview"}:
            continue  # Retired local worker snapshots are never discoverable skills.
        if not folder.is_dir() or not path.is_file():
            continue
        name = folder.name
        if not _NAME.fullmatch(name):
            raise ValueError(f"Invalid skill folder {name!r}: use 1–32 lowercase letters, digits, '-' or '_'.")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Skill {name!r} points outside the bundled skills directory.")
        # Hermes maps Telegram underscores back to hyphens at dispatch time.
        command = name.replace("_", "-")
        if command in commands:
            raise ValueError(f"Skills collide on command /{command} after Telegram normalization.")
        commands.add(command)
        skills.append((name, command, path))
    return skills


def _gateway_injection_state():
    """The effective gateway-injection value from the Kit entry."""
    try:
        from hermes_cli.config import read_raw_config
        policy = _KIT_COMPAT.peer(globals(), 'runtime_defaults')
        raw = read_raw_config() or {}
        value = policy.plugin_entry(raw).get('allow_gateway_injection')
        entries = ((raw.get('plugins') or {}).get('entries') or {}) if isinstance(raw, dict) else {}
        canonical = (entries.get(policy.PLUGIN) or {}).get('allow_gateway_injection')
    except Exception:
        return None, None
    return (value if isinstance(value, bool) else None,
            canonical if isinstance(canonical, bool) else None)


def _invoke(ctx, name, path, raw_args, namespace="kit"):
    from gateway.session_context import get_session_env

    if not path.is_file():
        return f"Skill {name!r} no longer exists. Update the plugin and restart Hermes."
    public = name
    mode = ""
    if namespace == "kit" and name == "grill-me" and (SKILLS_DIR / "plan-with-me/SKILL.md").is_file():
        public = "plan-with-me"
        mode = "Selected mode: challenge\n\n"
    planning = namespace == "kit" and (
        public in {"plan-for-me", "plan-with-me", "unslop"}
        or (name == "autoresearch" and (
            raw_args.startswith("Selected subcommand: plan\n")
            or (raw_args.split()[:1] == ["plan"])))
    )
    boundary = (
        "Before planning, read ../shared/RESEARCH-PLAN.md relative to the loaded "
        "skill directory. Its artifact/authority contract governs this request; "
        "supporting methods add no execution authority.\n\n"
    ) if planning else ""
    prompt = (
        f"The user invoked the /{name} skill command. "
        f'Load skill_view(name="{namespace}:{public}") and follow its instructions '
        "to perform the requested work in this conversation. "
        "Resolve supporting files relative to that skill's directory.\n\n"
        f"{boundary}{mode}User arguments:\n{raw_args}"
    )
    if namespace == "kit" and name in {"autoresearch", "plan-for-me", "unslop"}:
        prompt = (
            "GitHub Issues are the executable backlog. By default, publish actionable "
            "research/planning findings through the shared Plan Handoff contract; "
            "reuse existing issues and preserve dependencies and user ordering. Explicit "
            "read-only, chat-only, no-write and --dry-run requests write nothing. "
            "Planning alone does not authorize implementation or timed scheduling.\n\n"
        ) + prompt
    platform = get_session_env("HERMES_SESSION_PLATFORM")
    chat_id = get_session_env("HERMES_SESSION_CHAT_ID")
    target = {}
    if platform and chat_id:
        # Origin routing also works when this is the first message in a chat.
        # Hermes retains profile ownership and applies gateway admission rules.
        origin = {"platform": platform, "chat_id": chat_id}
        for field in ("chat_type", "chat_name", "thread_id", "user_id", "user_id_alt",
                      "user_name", "scope_id", "parent_chat_id", "message_id", "profile"):
            value = get_session_env(f"HERMES_SESSION_{field.upper()}")
            if value:
                origin[field] = value
        target["origin"] = origin
    elif session_key := get_session_env("HERMES_SESSION_KEY"):
        target["session_key"] = session_key
    if ctx.inject_message(prompt, **target):
        return None
    effective, _ = _gateway_injection_state()
    policy = _KIT_COMPAT.peer(globals(), 'runtime_defaults')
    setting = f"plugins.entries.{policy.PLUGIN}.allow_gateway_injection"
    if effective is False:
        return (
            f"Skill {name!r} was not started. {setting} is false in this profile's "
            f"config.yaml; set it true and restart its gateway."
        )
    if effective is True:
        return (
            f"Skill {name!r} was not started. {setting} is true, but Hermes did not "
            "accept the message; check its gateway logs."
        )
    return (
        f"Skill {name!r} was not started. For Telegram/gateway use, set "
        f"{setting}: true in this profile's config.yaml and restart "
        "its gateway. If already enabled, check Hermes gateway logs."
    )


def register(ctx):
    """Hermes plugin entry point; called again on plugin load after a restart."""
    from hermes_cli.commands import resolve_command
    from hermes_cli.plugins import get_plugin_commands

    skills = _discover_skills()
    from hermes_constants import get_hermes_home
    install = _KIT_COMPAT.peer(globals(), 'install_skills').install
    native_skills = [path.parent for _, _, path in skills]
    shared = SKILLS_DIR / 'shared'
    if shared.is_dir():
        native_skills.append(shared)
    # The engineering pack is a reference tree, not a registered skill: install it
    # beside the skills so links from retained workflows resolve, without a
    # command or skill entry that invites direct use.
    engineering = SKILLS_DIR / 'engineering'
    if engineering.is_dir():
        native_skills.append(engineering)
    messages = []
    if install(SKILLS_DIR, [('current', get_hermes_home())], skills=native_skills, report=messages.append):
        # Commands load skills by qualified name, so a preserved native folder must not block them.
        logger.warning('Bundled native skill provisioning incomplete:\n%s', '\n'.join(messages))
    policy = _KIT_COMPAT.peer(globals(), 'runtime_defaults')
    policy.apply_runtime_defaults(ctx)
    existing = get_plugin_commands()
    for name, command, path in skills:
        # Canonical folders own the current skill identities.
        if name != "grill-me" or not any(n == "plan-with-me" for n, _, _ in skills):
            ctx.register_skill(name, path)
        if name in {"docs-sync", "plan-with-me", "plan-for-me", "update-kit"}:
            continue  # workflow_commands reserves both public spellings atomically.
        if resolve_command(command) is not None or command in existing:
            logger.warning("Skipping /%s: command already exists; use skill_view('kit:%s').",
                           command, name)
            continue
        handler = partial(_invoke, ctx, name, path)
        ctx.register_command(
            command, handler,
            description={
                "git-commit-push": "Commit current branch, sync and push its upstream.",
                "push": "Save this checkout, pull and deliver to main.",
            }.get(name, f"Run the {name} skill"),
            args_hint="<instructions>" if name in {"autoresearch", "grill-me"} else "[instructions]",
        )
    _KIT_COMPAT.peer(globals(), 'autoresearch_commands').register(ctx, skills, _invoke)
    _KIT_COMPAT.peer(globals(), 'workflow_commands').register(ctx, skills, _invoke)
    _KIT_COMPAT.peer(globals(), 'bundle').register_bundle(ctx, _invoke)
