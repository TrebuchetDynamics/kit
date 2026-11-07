"""Apply bundle policy and command visibility in Hermes' bound profile."""
import logging
from pathlib import Path
PLUGIN = 'kit'
LEGACY_PLUGIN = 'autowork'
BUNDLE_SKILLS = _AUTOWORK_LAYOUT.root / 'skills'
logger = logging.getLogger(__name__)
_reported_legacy_entry = set()


def _plugin_entries(raw):
    entries = ((raw.get('plugins') or {}).get('entries') or {}) if isinstance(raw, dict) else {}
    return entries if isinstance(entries, dict) else {}


def _report_legacy_entry(raw):
    """Report a profile carrying both keys once; canonical values still win per key."""
    entries = _plugin_entries(raw)
    if PLUGIN not in entries or LEGACY_PLUGIN not in entries:
        return
    marker = (PLUGIN, LEGACY_PLUGIN)
    if marker in _reported_legacy_entry:
        return
    _reported_legacy_entry.add(marker)
    logger.warning(
        'Profile carries both plugins.entries.%s and plugins.entries.%s; using %s values '
        'where present and %s for missing keys.',
        PLUGIN, LEGACY_PLUGIN, PLUGIN, LEGACY_PLUGIN)


def skills_patch(raw):
    """Keep user-disabled skills while enabling this bundle's own skills."""
    skills_config = raw.get('skills') if isinstance(raw, dict) else None
    current = skills_config.get('disabled') if isinstance(skills_config, dict) else None
    current = [n for n in current if isinstance(n, str)] if isinstance(current, list) else []
    bundled = {p.parent.name for p in BUNDLE_SKILLS.glob('*/SKILL.md')}
    return sorted(set(current) - bundled)


def plugin_entry(raw):
    """This plugin's `plugins.entries` block: canonical keys, then legacy keys it lacks.

    A profile may carry both entries while the rename is in progress. Reading only the
    canonical entry would drop an opt-out or custom setting that still lives
    under the legacy key, so fall back per key (and per `settings`/`config` key) and
    let the canonical value win wherever both define one.
    """
    entries = _plugin_entries(raw)
    _report_legacy_entry(raw)
    legacy = entries.get(LEGACY_PLUGIN)
    canonical = entries.get(PLUGIN)
    legacy = legacy if isinstance(legacy, dict) else {}
    if not isinstance(canonical, dict):
        return legacy
    entry = {**legacy, **canonical}
    for subtree in ('settings', 'config'):
        old, new = legacy.get(subtree), canonical.get(subtree)
        if isinstance(old, dict) and isinstance(new, dict):
            entry[subtree] = {**old, **new}
    return entry


def expected_settings(raw):
    """Bundle policy for one profile's raw config: approvals, turn budget, injection and menu."""
    defaults = _AUTOWORK_COMPAT.peer(globals(), 'bundle').defaults
    menu_patch = _AUTOWORK_COMPAT.peer(globals(), 'telegram_menu_policy').menu_patch

    settings = defaults()
    wanted = settings['hermes']
    patch = {
        'approvals': {
            'mode': wanted['approvals_mode'],
            'destructive_slash_confirm': wanted['destructive_slash_confirm'],
            'mcp_reload_confirm': wanted['mcp_reload_confirm'],
        },
        # Hermes quick setup writes a 90-iteration cap that cuts Autowork turns short.
        'agent': {'max_turns': wanted['max_turns']},
        # Writes go to the canonical entry only; reads accept the legacy entry.
        'plugins': {'entries': {
            PLUGIN: {'allow_gateway_injection': wanted['allow_gateway_injection']},
        }},
    }
    patch.update(menu_patch(raw))
    disabled = skills_patch(raw)
    current = (raw.get('skills') or {}).get('disabled') if isinstance(raw, dict) and isinstance(raw.get('skills'), dict) else None
    # Write only changes; preserve external skill settings.
    if disabled != (current or []):
        patch['skills'] = {'disabled': disabled}
    return patch


def settings_drift(raw, expected, prefix=(), root=None):
    """Dotted paths whose effective value differs from the expected leaf value."""
    root = raw if root is None else root
    drift = []
    for key, value in expected.items():
        path = prefix + (key,)
        if prefix == ('plugins', 'entries') and key == PLUGIN:
            actual = plugin_entry(root)
        else:
            actual = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(value, dict):
            drift += settings_drift(actual, value, path, root)
        elif type(actual) is not type(value) or actual != value:
            drift.append('.'.join(path))
    return drift


def _leaf_paths(expected, prefix=()):
    for key, value in expected.items():
        if isinstance(value, dict):
            yield from _leaf_paths(value, prefix + (key,))
        else:
            yield prefix + (key,)


def _opted_out(raw):
    """Mirror Hermes' ctx.get_config: `settings.<key>`, then the legacy `config.<key>`."""
    entry = plugin_entry(raw)
    for subtree in ('settings', 'config'):
        values = entry.get(subtree)
        if isinstance(values, dict) and 'apply_runtime_defaults' in values:
            return values['apply_runtime_defaults'] is False
    return False


def setup_opted_out(config_path):
    """Setup-time `_opted_out` for one profile config: True, False or None (unknown).

    Parses with PyYAML, the loader Hermes reads config with. A missing,
    unreadable or malformed config is not an opt-out: setup proceeds and
    Hermes refuses the write as before. Without PyYAML, a config that never
    names the setting cannot opt out; one that does is unknown, never applied.
    """
    try:
        text = Path(config_path).read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return False
    try:
        import yaml
    except ImportError:
        return None if 'apply_runtime_defaults' in text else False
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return _opted_out(raw)


def opted_out_settings(raw):
    """What an opted-out profile still receives: the bundle's own Telegram menu entries.

    The opt-out keeps a profile's approval, turn, injection and skill settings. Every
    profile had opted out, which also froze the menu, so commands added since (/blockers)
    never reached a Telegram menu."""
    return _AUTOWORK_COMPAT.peer(globals(), 'telegram_menu_policy').menu_patch(raw)


def apply_runtime_defaults(ctx):
    # Read raw YAML, refusing malformed settings rather than overwriting them
    # with fallback defaults. The native loader binds the owning profile even
    # when a shared gateway loads several profiles in the same process.
    try:
        from hermes_cli.config import require_readable_config_before_write, save_config
        raw = require_readable_config_before_write()
    except Exception:
        # An opted-out profile never failed to load over its unreadable config.
        if ctx.get_config('apply_runtime_defaults', True) is False:
            return
        raise
    # This opt-out must be read from either settings key; otherwise the next load
    # deliberately reapplies the bundle policy.
    opted_out = _opted_out(raw)
    patch = opted_out_settings(raw) if opted_out else expected_settings(raw)
    if settings_drift(raw, patch):
        # Merge under Hermes' config lock, preserving unrelated settings and
        # deny rules. Keep false values explicit even if upstream defaults change.
        save_config(patch, merge_existing=True, preserve_keys=set(_leaf_paths(patch)))


def verify_runtime_defaults():
    """Re-read the bound profile after load; [] when its settings match. An opted-out profile
    is checked only for the bundle's menu entries."""
    from hermes_cli.config import read_raw_config
    raw = read_raw_config() or {}
    return settings_drift(raw, opted_out_settings(raw) if _opted_out(raw) else expected_settings(raw))


CRON_SCRIPTS = ('cron-autowork/scripts/autowork-start-notice.py',)
MANAGED = b'# autowork: '


def provision_cron_scripts(skills_dir, home):
    """Copy bundle cron scripts into HERMES_HOME/scripts, where Hermes requires them.

    Hermes refuses cron scripts that resolve outside the profile's scripts folder,
    so a symlink to the bundle cannot work. A same-named file without the bundle
    marker belongs to the user and is left alone. Returns the names it could not
    provision.
    """
    target_dir = Path(home) / 'scripts'
    if target_dir.is_symlink():
        return [Path(rel).name for rel in CRON_SCRIPTS]
    skipped = []
    for rel in CRON_SCRIPTS:
        source = Path(skills_dir) / rel
        target = target_dir / source.name
        if not source.is_file():
            continue
        data = source.read_bytes()
        if target.is_symlink() or (target.exists() and MANAGED not in target.read_bytes()[:200]):
            skipped.append(source.name)
            continue
        if target.exists() and target.read_bytes() == data:
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f'.{target.name}.tmp')
        temporary.write_bytes(data)
        temporary.chmod(0o755)
        temporary.replace(target)
    return skipped
