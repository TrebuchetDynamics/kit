"""Bundle setup, imported skill aliases, and read-only command diagnostics."""

from functools import partial
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = _KIT_LAYOUT.root
PLUGIN_NAME = 'kit'
OWNER_NAMES = (PLUGIN_NAME,)


def defaults():
    return json.loads((ROOT / 'plugins/defaults.json').read_text(encoding='utf-8'))


def record_skill_repository(home, source, names):
    """Record expected imports before installation so partial setup stays visible."""
    path = Path(home) / '.toolset-imports.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    state[source] = sorted(names)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(path)


def missing_skill_imports(home, command_names):
    path = Path(home) / '.toolset-imports.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    expected = set(defaults()['required_skills'])
    missing_sources = []
    for line in (ROOT / 'plugins/PLUGINS.md').read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == 'skills':
            if fields[1] not in state:
                missing_sources.append(fields[1])
            expected.update(state.get(fields[1], []))
    return sorted(expected - command_names), missing_sources


def _alias(name):
    name = re.sub(r'[^a-z0-9-]', '-', name.lower().replace('_', '-')).strip('-')
    if len(name) > 32:
        name = name[:23] + '-' + hashlib.sha256(name.encode()).hexdigest()[:8]
    return name


def register_imported_skills(ctx, invoke):
    from hermes_cli.commands import resolve_command
    from hermes_cli.plugins import get_plugin_commands, get_plugin_manager

    manager = get_plugin_manager()
    commands = get_plugin_commands()
    allowed = defaults()['imported_plugins']
    aliases = {}
    for info in manager.list_plugin_skill_metadata():
        namespace, sep, name = info['name'].partition(':')
        if not sep or namespace not in allowed:
            continue
        if info.get('frontmatter', {}).get('user-invocable') is False:
            continue
        command = _alias(name)
        # Keep an upstream native command when it already implements this skill.
        if command in commands and commands[command].get('plugin') == namespace:
            continue
        if not command or resolve_command(command) is not None or command in commands:
            command = _alias(f'{namespace}-{name}')
        if not command or resolve_command(command) is not None or command in commands:
            continue
        path = manager.find_plugin_skill(info['name'])
        if path is None or not path.is_file():
            continue
        ctx.register_command(command, partial(invoke, ctx, name, path, namespace=namespace),
                             description=f"Run {info['name']}", args_hint='[instructions]')
        aliases[command] = info['name']
    return aliases


def inventory():
    from hermes_cli.plugins import get_plugin_commands, get_plugin_manager
    from hermes_cli.commands_platforms import telegram_menu_commands, telegram_menu_max_commands
    from agent.skill_commands import get_skill_commands

    manager = get_plugin_manager()
    manager.discover_and_load()
    plugins = manager.list_plugins()
    required = set(defaults()['imported_plugins']) | {PLUGIN_NAME}
    # Older installs can still own Ponytail commands; report them, never require them.
    wanted = required | {'ponytail'}
    rows = []
    for name, item in sorted(get_plugin_commands().items()):
        if item.get('plugin') in wanted:
            rows.append({'command': name, 'telegram': name.replace('-', '_'),
                         'source': item['plugin'], 'kind': 'plugin'})
    for name, item in sorted(get_skill_commands().items()):
        name = name.lstrip('/')
        rows.append({'command': name, 'telegram': name.replace('-', '_'),
                     'source': item.get('name', name), 'kind': 'skill'})
    menu_limit = telegram_menu_max_commands()
    menu, hidden = telegram_menu_commands(max_commands=menu_limit)
    menu_names = dict(menu)
    for row in rows:
        row['in_telegram_menu'] = row['telegram'] in menu_names
    selected = [dict(p) for p in plugins if p['name'] in wanted]
    loaded = {p['name'] for p in selected if p.get('enabled') and not p.get('error')}
    missing_skills, unchecked_sources = missing_skill_imports(
        manager.home_path, {row['command'] for row in rows})
    return {'plugins': selected, 'missing_plugins': sorted(required - loaded),
            'plugin_skills': sorted(info['name'] for info in manager.list_plugin_skill_metadata()
                                    if info['name'].partition(':')[0] in wanted),
            'missing_skills': missing_skills, 'unchecked_skill_sources': unchecked_sources,
            'commands': rows, 'telegram_menu_hidden': hidden, 'telegram_menu_limit': menu_limit,
            'note': 'Menu capacity is limited; typed commands remain available; inspect hermes kit doctor --json.'}


def update_home():
    from hermes_constants import get_hermes_home
    home = Path(get_hermes_home()).expanduser()
    return home.parent.parent if home.parent.name == 'profiles' else home


def _updater():
    """The updater peer from this captured release, like its subprocess entry."""
    return _KIT_COMPAT.peer(globals(), 'update_bundle')


def linked_profiles():
    """Profiles whose plugin links to a working checkout, or None when that cannot be read."""
    try:
        return _updater().fleet_linked_profiles(update_home())
    except (Exception, SystemExit):
        return None


def linked_lines(rows):
    if not rows:
        return []
    names = ', '.join(r['profile'] for r in rows)
    targets = ', '.join(sorted({r['target'] for r in rows}))
    return [f'Linked to a working checkout ({targets}); any gateway restart loads its current files: {names}',
            'Preview pinning one to its current revision: hermes kit pin NAME --dry-run']


def setup_parser(parser):
    actions = parser.add_subparsers(dest='action', required=True)
    update = actions.add_parser('update', help='Update this bundle and native skills across all existing profiles')
    update.add_argument('--check', action='store_true', help='Fetch/check only; no checkout/profile updates')
    update.add_argument('--hermes-home', help='Hermes root containing profiles/')
    setup = actions.add_parser('setup', help='Install, enable, and configure sources in plugins/PLUGINS.md')
    setup.add_argument('--dry-run', action='store_true')
    setup.add_argument('--hermes-home', help='Hermes root containing profiles/')
    setup.add_argument('--yes-deps', action='store_true', help='Consent to declared Python dependencies')
    setup.add_argument('--bundle-only', action='store_true')
    setup.add_argument('--no-reload', action='store_true')
    finalize = actions.add_parser('finalize', help='Verify this profile and refresh gateway command wiring')
    finalize.add_argument('--hermes-home', required=True)
    finalize.add_argument('--bundle-only', action='store_true')
    finalize.add_argument('--no-reload', action='store_true')
    pin = actions.add_parser('pin', help="Replace a profile's plugin link with a clone of the same revision")
    # Positional: Hermes consumes a global --profile/-p before the subcommand sees it.
    pin.add_argument('profile', metavar='PROFILE')
    pin.add_argument('--dry-run', action='store_true', help='Report what would change; write nothing')
    pin.add_argument('--unpin', action='store_true', help='Restore the link saved by the last pin')
    pin.add_argument('--hermes-home', help='Hermes root containing profiles/')
    doctor = actions.add_parser('doctor', help='Report enabled plugins and available commands')
    doctor.add_argument('--json', action='store_true')
    doctor.add_argument('--core', '--bundle-only', dest='core_only', action='store_true',
                        help='Check bundled skills/commands; report external gaps without failing on them')


def diagnose(report, *, core_only=False):
    """Evaluate one inventory snapshot without invoking setup or reloading gateways."""
    errors = []
    own = next((p for p in report['plugins'] if p['name'] in OWNER_NAMES), {})
    if not own.get('enabled') or own.get('error'):
        errors.append('kit is not loaded cleanly')
    names = {p.parent.name for p in (ROOT / 'skills').glob('*/SKILL.md')
             if p.parent.name not in {'repo-docs', 'repo-interview'}}
    commands = {r['command'] for r in report['commands']
                if r.get('kind') == 'plugin' and r.get('source') in OWNER_NAMES}
    fallbacks = _KIT_COMPAT.peer(globals(), 'setup_runtime').bundled_skill_fallbacks(report) & names
    missing_commands = sorted(n.replace('_', '-') for n in names
                              if n.replace('_', '-') not in commands | fallbacks)
    public_names = set()
    for name in names:
        if name == 'grill-me' and 'plan-with-me' in names:
            continue  # Challenge mode is exposed through Plan With Me.
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        match = re.search(r'^name: ([a-z0-9_-]+)$', text, re.MULTILINE)
        public_names.add(match.group(1) if match else name)
    missing_skills = sorted('kit:' + n for n in public_names
                            if 'kit:' + n not in report['plugin_skills'])
    if not names:
        errors.append('No bundled skills found')
    if missing_commands:
        errors.append('Unavailable bundled commands: ' + ', '.join(missing_commands))
    if missing_skills:
        errors.append('Unavailable bundled skills: ' + ', '.join(missing_skills))
    gaps = {field: [name for name in report[field] if name not in OWNER_NAMES]
            for field in ('missing_plugins', 'missing_skills', 'unchecked_skill_sources')}
    integrations_ready = not any(gaps.values())
    ready = not errors and (core_only or integrations_ready)
    return {**report, 'scope': 'core' if core_only else 'full',
            'status': 'ready' if ready else 'incomplete',
            'core_status': 'incomplete' if errors else 'ready', 'core_errors': errors,
            'bundled_skill_fallbacks': sorted('kit:' + name for name in fallbacks),
            'integrations_status': 'ready' if integrations_ready else 'unavailable',
            'integration_gaps': gaps,
            'readiness_note': 'Skill and command registration only. Model execution, workflow-specific '
                              'tools and live Telegram delivery are not tested.'}


def format_diagnosis(report):
    lines = [f"Kit — {report['scope']} check: {report['status']}",
             f"Core: {report['core_status']} (bundled skill and command registration)",
             f"Integrations: {report['integrations_status']}"]
    lines.extend('  ' + error for error in report['core_errors'])
    if report.get('bundled_skill_fallbacks'):
        lines.append('Existing native or Ponytail commands are unchanged; invoke bundled skills: ' +
                     ', '.join(report['bundled_skill_fallbacks']))
    for field, names in report['integration_gaps'].items():
        if names:
            lines.append('  ' + field.replace('_', ' ') + ': ' + ', '.join(names))
    if report['scope'] == 'core' and report['integrations_status'] != 'ready':
        lines.append('External gaps do not fail this core check; workflows using them may be unavailable.')
    lines += linked_lines(report.get('linked_profiles'))
    lines.append(report['readiness_note'])
    return '\n'.join(lines)


def handle_cli(args):
    if args.action == 'update':
        argv = [sys.executable, str(ROOT / 'scripts/update_bundle.py'), '--hermes-home',
                str(args.hermes_home or update_home())]
        if args.check:
            argv.append('--check')
        return subprocess.run(argv, cwd=ROOT, check=False).returncode
    if args.action == 'pin':
        argv = [sys.executable, str(ROOT / 'scripts/update_bundle.py'), '--hermes-home',
                str(args.hermes_home or update_home()), '--unpin-profile' if args.unpin else '--pin-profile', args.profile]
        if args.dry_run:
            argv.append('--dry-run')
        return subprocess.run(argv, cwd=ROOT, check=False).returncode
    if args.action == 'doctor':
        report = inventory()
        linked = linked_profiles()
        if linked is not None:
            report = {**report, 'linked_profiles': linked}
        report = diagnose(report, core_only=getattr(args, 'core_only', False))
        print(json.dumps(report, indent=2) if args.json else format_diagnosis(report))
        return int(report['status'] != 'ready')
    if args.action == 'finalize':
        finalize = _KIT_COMPAT.peer(globals(), 'setup_runtime').finalize
        report = inventory()
        result, code = finalize(ROOT, report, args)
        if os.environ.get('KIT_INSTALL_HERMES_SUMMARY') == '1':
            home = Path(result['home']) if 'home' in result else None
            profile = ('verification' if home is None else
                       'default' if home == Path(args.hermes_home) else home.name)
            print(f"Profile {profile}: {result['status']}; settings {result.get('settings', 'not checked')}; "
                  f"gateway {result.get('gateway', 'not checked')}", flush=True)
            for error in result.get('errors', []):
                print(f'Failed: {profile}: {error}', flush=True)
            if note := result.get('note'):
                print(f'Note: {profile}: {note}', flush=True)
        else:
            print(json.dumps(result, indent=2))
        return code
    argv = ['python3', str(ROOT / 'scripts/setup_bundle.py')]
    for flag in ('dry_run', 'yes_deps', 'bundle_only', 'no_reload'):
        if getattr(args, flag, False): argv.append('--' + flag.replace('_', '-'))
    if args.hermes_home: argv += ['--hermes-home', args.hermes_home]
    return subprocess.run(argv, cwd=ROOT, check=False).returncode


def register_bundle(ctx, invoke):
    from hermes_cli.plugins import get_plugin_manager

    register_imported_skills(ctx, invoke)
    # Hermes leases CLI slots by replacement; keep another plugin's owner just
    # as we keep foreign chat commands. Never force a maintenance takeover.
    existing = get_plugin_manager()._cli_commands.get('kit')
    if existing is not None and existing.get('plugin') not in OWNER_NAMES:
        logging.getLogger(__name__).warning('Skipping hermes kit: CLI command already exists (owner: %s).',
                                            existing.get('plugin'))
        return
    ctx.register_cli_command('kit', help='Install, update and diagnose the Kit bundle',
                             setup_fn=setup_parser, handler_fn=handle_cli)
