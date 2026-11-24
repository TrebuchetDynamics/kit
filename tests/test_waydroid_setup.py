"""Isolated provisioning entrypoint tests; no real sudo, services or devices."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'waydroid-universal-setup.sh'

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
root = Path(os.environ['FIXTURE'])
with (root / 'calls').open('a') as f:
    f.write(name + ' ' + ' '.join(args) + '\n')
mode = os.environ.get('MODE', '')
session_file = root / 'session'
session = session_file.read_text() if session_file.exists() else ('gui' if mode.startswith('gui') else 'stopped')
if name == 'timeout':
    if mode == 'gui-stop-hang' and args[1:] == ['waydroid', 'session', 'stop']:
        sys.exit(124)  # deterministic timeout contract, no sleeping/hung test
    # Preserve the installed name: multicall coreutils reject renamed links.
    os.execv(os.environ['REAL_TIMEOUT'], ['timeout', *args])
elif name == 'busctl':
    if args == ['--system', '--auto-start=no', '--timeout=10', 'call',
                'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                'NameHasOwner', 's', 'id.waydro.Container']:
        if mode == 'manager-owner-failure': sys.exit(1)
        print('b false' if mode == 'manager-absent' or (root / 'manager-lost').exists() else 'b true'); sys.exit(0)
    assert args == ['--system', '--auto-start=no', '--timeout=10', '--json=short', 'call',
                    'id.waydro.Container', '/ContainerManager', 'id.waydro.ContainerManager', 'GetSession']
    if mode == 'gui-bus-failure' and (root / 'stop-attempted').exists(): sys.exit(1)
    if mode == 'gui-malformed-bus':
        print('{}'); sys.exit(0)
    if mode == 'gui-release-delay' and session == 'releasing':
        session_file.write_text('stopped')
    data = {} if session == 'stopped' else {
        'user_id': '2000' if session == 'foreign' else '1000',
        'wayland_display': 'wayland-kit' if session == 'managed' or mode == 'gui-display-conflict' else 'wayland-0',
        'pid': '123' if session != 'changed' else '456'}
    if mode == 'gui-missing-owner': data.pop('user_id', None)
    with (root / 'calls').open('a') as f:
        f.write('bus-reply ' + ('session' if data else 'empty') + '\n')
    print(json.dumps({'type': 'a{ss}', 'data': [data]}))
elif name == 'id':
    print('1000' if '-u' in args else 'tester')
elif name == 'uname':
    print(('Darwin' if mode == 'not-linux' else 'Linux') if '-s' in args else ('riscv64' if mode == 'no-arch' else 'x86_64'))
elif name == 'modinfo':
    sys.exit(1 if mode == 'no-binder' else 0)
elif name == 'sudo':
    if args == ['-v']:
        (root / 'sudo-admitted').touch()
        if mode == 'gui-sudo-fail': sys.exit(1)
        if mode == 'gui-sudo-race': session_file.write_text('foreign')
        sys.exit(0)
    if args == ['-n', '-v']: sys.exit(0)
    if args[0] == '--': args = args[1:]
    os.execvp(args[0], args)
elif name == 'flock' and mode == 'gui-lock-manager-loss':
    (root / 'manager-lost').touch()
elif name == 'flock' and mode in ['gui-lock-race', 'gui-lock-same-uid-race']:
    session_file.write_text('foreign' if mode == 'gui-lock-race' else 'changed')
elif name == 'flock' and mode == 'peer-completed':
    # Another setup finishes after the read-only admission snapshot, before lock.
    import subprocess
    state = root / 'var/lib/waydroid'
    state.mkdir(parents=True, exist_ok=True)
    (state / 'waydroid.cfg').write_text('[properties]\nro.hardware.egl = swiftshader\n')
    subprocess.run([str(root / 'bin/waydroid'), 'init'], check=True, timeout=5)
    (state / 'data').mkdir()
    (state / 'overlay_rw/system').mkdir(parents=True)
    (state / 'overlay_rw/system/sentinel').write_text('keep overlay')
    (root / 'calls').write_text('')
elif name == 'waydroid':
    if args == ['--help']:
        print('init status session prop show-full-ui')
    elif args[0] == 'init':
        if mode == 'false-init': sys.exit(0)
        state = root / 'var/lib/waydroid'
        state.mkdir(parents=True, exist_ok=True)
        (state / 'images').mkdir(exist_ok=True)
        for image in ['system', 'vendor']:
            p = state / 'images' / (image + '.img')
            if not p.exists(): p.write_bytes(b'\0' * 1080 + b'\x53\xef' + b'\0' * 1024)
        # Upstream images.get removes existing writable overlays during init.
        import shutil
        shutil.rmtree(state / 'overlay_rw', ignore_errors=True)
        # Real init consumes the pre-init rendering config into base properties.
        cfg = (state / 'waydroid.cfg').read_text()
        assert 'ro.hardware.egl = swiftshader' in cfg
        (state / 'waydroid_base.prop').write_text('ro.hardware.egl=swiftshader\n')
        (state / 'rootfs').mkdir(exist_ok=True)
        (state / 'lxc/waydroid').mkdir(parents=True, exist_ok=True)
        (state / 'lxc/waydroid/config').write_text('lxc config')
        (state / 'waydroid.cfg').write_text('[waydroid]\nimages_path = ' + str(state / 'images') + '\nsystem_datetime = 1\nvendor_datetime = 1\n')
    elif args == ['session', 'stop']:
        (root / 'stop-attempted').touch()
        if mode == 'gui-stop-fail': sys.exit(1)
        if mode not in ['gui-no-release', 'gui-bus-failure', 'gui-stopped-lie']:
            session_file.write_text('releasing' if mode == 'gui-release-delay' else 'stopped')
    elif args[0] == 'status':
        count = root / 'ip-count'
        n = int(count.read_text()) if count.exists() else 0
        count.write_text(str(n+1))
        ip = 'UNKNOWN' if mode == 'no-ip' or (mode == 'slow-ip' and n == 0) else '192.0.2.8'
        if mode == 'gui-stopped-lie' and (root / 'stop-attempted').exists():
            print('Session:\tSTOPPED')
        elif session == 'stopped': print('Session:\tSTOPPED\nIP address:\t' + ip)
        else:
            owner = '' if mode == 'gui-missing-owner' else ('2000' if session == 'foreign' else '1000')
            display = 'wayland-kit' if session == 'managed' or mode == 'gui-display-conflict' else 'wayland-0'
            print('Session:\tRUNNING\nContainer:\tRUNNING\nIP address:\t' + ip +
                  '\nSession user:\ttester(' + owner + ')\nWayland display:\t' + display)
elif name == 'adb':
    if args[0] == 'devices':
        state = 'unauthorized' if mode.endswith('unauthorized') else 'device'
        print('List of devices attached\n192.0.2.8:5555\t' + state)
    elif 'getprop' in args:
        key = args[-1]
        if mode.endswith('properties-failed') and key != 'sys.boot_completed': sys.exit(1)
        if mode == 'gui-adb-owner-race' and key == 'ro.product.cpu.abi': session_file.write_text('foreign')
        print({'sys.boot_completed': '0' if mode.endswith('boot-timeout') else '1', 'ro.build.version.release': '13', 'ro.product.cpu.abi': 'x86_64'}[key])
elif name == 'weston':
    if '--help' in args:
        print('unsupported' if mode == 'gui-no-weston' else '--backend --use-pixman headless --socket --no-config')
    else:
        import socket, time
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(str(root / 'run/wayland-kit'))
        time.sleep(8)
elif name == 'apt-cache':
    sys.exit(1 if mode == 'no-package' else 0)
elif name == 'dnf' and 'list' in args:
    sys.exit(1 if mode == 'no-package' else 0)
elif name in ['apt-get', 'dnf']:
    for package in args[2:]:
        p = root / 'bin' / ('adb' if package == 'android-tools' else package)
        p.write_text(Path(sys.argv[0]).read_text())
        p.chmod(0o755)
elif name == 'systemctl':
    if 'show' in args and 'LoadState' in ' '.join(args): print('loaded')
    if 'FragmentPath' in ' '.join(args):
        unit = root / 'home/.config/systemd/user/kit-waydroid.service'
        print('/foreign/kit-waydroid.service' if mode == 'gui-foreign-unit' else (str(unit) if unit.exists() else ''))
    if 'ActiveState' in ' '.join(args):
        print('activating' if mode == 'gui-unit-activating' else ('active' if session == 'managed' else 'inactive'))
    if args == ['--user', 'enable', '--now', 'kit-waydroid.service']:
        if mode == 'gui-start-fail': sys.exit(1)
        if mode != 'gui-start-unconfirmed':
            session_file.write_text('foreign' if mode == 'gui-start-foreign' else 'managed')
    if mode == 'gui-start-race' and args == ['--user', 'daemon-reload']:
        session_file.write_text('foreign')
elif name == 'loginctl':
    pass
'''


class WaydroidSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ['bash', 'cat', 'python3', 'timeout', 'readlink', 'awk', 'tr', 'sed', 'grep', 'mkdir', 'flock', 'sleep', 'mktemp', 'rm', 'install']:
            (self.bin / name).symlink_to(shutil.which(name))
        for name in ['timeout', 'flock']:
            (self.bin / name).unlink()
            (self.bin / name).write_text(FAKE)
            (self.bin / name).chmod(0o755)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.state = self.base / 'var/lib/waydroid'
        self.run = self.base / 'run'
        (self.run / 'systemd/system').mkdir(parents=True)
        # Replace fixed host paths only in a private copy, not through production overrides.
        text = SCRIPT.read_text()
        for p in ['/var/lib/waydroid', '/etc/systemd/system', '/run/systemd/system', '/sys/module/binder_linux', '/dev/binder']:
            text = text.replace(p, str(self.base) + p)
        self.script = self.base / 'setup.sh'
        self.script.write_text(text)
        self.script.chmod(0o755)
        for name in ['busctl', 'id', 'uname', 'sudo', 'systemctl', 'loginctl', 'waydroid', 'weston', 'adb', 'modinfo', 'apt-cache', 'apt-get']:
            p = self.bin / name
            p.write_text(FAKE)
            p.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_DATA_HOME=str(self.home / '.local/share'), XDG_RUNTIME_DIR=str(self.run),
                        PATH=str(self.bin), FIXTURE=str(self.base), REAL_TIMEOUT=shutil.which('timeout'))

    def invoke(self, *args, mode='', cwd=None):
        result = subprocess.run([str(self.script), *args], env=dict(self.env, MODE=mode),
                                cwd=cwd or self.base, text=True, capture_output=True, timeout=15)
        return result

    def calls(self):
        p = self.base / 'calls'
        return p.read_text() if p.exists() else ''

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def complete_device(self):
        self.assert_ok(self.invoke())
        (self.base / 'calls').write_text('')
        (self.base / 'session').unlink()
        # Initial setup is complete, but no managed service is presently running.
        for path in ['data/sentinel', 'overlay_rw/system/sentinel']:
            p = self.state / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('keep')
        key = self.home / '.android/adbkey'
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text('private fixture key')
        return {p: p.read_bytes() for base in [self.state, key.parent]
                for p in base.rglob('*') if p.is_file()}

    def test_timeout_fixture_preserves_native_executable_name(self):
        native = self.base / 'native/timeout'
        native.parent.mkdir()
        native.write_text('#!/bin/sh\n'
                          '[ "${0##*/}" = timeout ] || exit 126\n'
                          'echo used > "$FIXTURE/native-timeout-used"\n'
                          'exec "$NATIVE_TIMEOUT" "$@"\n')
        native.chmod(0o755)
        self.env.update(NATIVE_TIMEOUT=self.env['REAL_TIMEOUT'], REAL_TIMEOUT=str(native))
        self.assert_ok(self.invoke('--check'))
        self.assertTrue((self.base / 'native-timeout-used').exists())

    def test_default_graphical_transfer_and_retry_preserve_device(self):
        before = self.complete_device()
        result = self.invoke(mode='gui-release-delay')
        self.assert_ok(result)
        self.assertIn('open GUI apps will be interrupted', result.stdout)
        calls = self.calls().splitlines()
        stop = calls.index('waydroid session stop')
        start = calls.index('systemctl --user enable --now kit-waydroid.service')
        self.assertEqual(calls.count('waydroid session stop'), 1)
        release = calls.index('bus-reply empty', stop + 1)
        self.assertLess(stop, release)
        self.assertLess(release, start)
        self.assertLess(start, calls.index('adb devices'))
        self.assertIn('bus-reply session', calls[start + 1:calls.index('adb devices')])
        self.assertEqual(calls.count('systemctl --user enable --now kit-waydroid.service'), 1)
        self.assertNotIn('sudo -- waydroid session stop', calls)
        self.assertNotIn('waydroid init ', self.calls())
        self.assertIn('ADB serial: 192.0.2.8:5555', result.stdout)
        self.assertIn('Android: 13', result.stdout)
        self.assertIn('ABI: x86_64', result.stdout)
        (self.base / 'calls').write_text('')
        self.assert_ok(self.invoke())
        self.assertNotIn('waydroid session stop', self.calls())
        self.assertNotIn('restart', self.calls())
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_check_plans_graphical_transfer_without_mutation(self):
        self.complete_device()
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        result = self.invoke('--check', mode='gui')
        self.assert_ok(result)
        self.assertIn('Planned same-user graphical transfer', result.stdout)
        self.assertNotIn('sudo ', self.calls())
        self.assertNotIn('session stop', self.calls())
        self.assertNotIn('enable --now', self.calls())
        self.assertNotIn('waydroid status', self.calls())
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_check_absent_or_unavailable_manager_never_activates_it(self):
        self.complete_device()
        for mode in ['manager-absent', 'manager-owner-failure']:
            with self.subTest(mode=mode):
                result = self.invoke('--check', mode=mode)
                if mode == 'manager-absent':
                    self.assert_ok(result)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('repair D-Bus', result.stderr)
                self.assertNotIn('waydroid status', self.calls())
                self.assertNotIn('sudo ', self.calls())
                self.assertNotIn('enable --now', self.calls())

    def test_transfer_admission_races_and_conflicts_never_stop(self):
        self.complete_device()
        for mode in ['gui-missing-owner', 'gui-display-conflict', 'gui-no-weston',
                     'gui-sudo-fail', 'gui-lock-race', 'gui-lock-same-uid-race',
                     'gui-sudo-race', 'gui-malformed-bus', 'gui-foreign-unit', 'gui-unit-activating',
                     'gui-lock-manager-loss']:
            with self.subTest(mode=mode):
                for name in ['session', 'sudo-admitted', 'manager-lost']:
                    (self.base / name).unlink(missing_ok=True)
                (self.base / 'calls').write_text('')
                result = self.invoke(mode=mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('waydroid session stop', self.calls())
                self.assertNotIn('enable --now', self.calls())
        (self.base / 'session').unlink(missing_ok=True)
        (self.base / 'manager-lost').unlink(missing_ok=True)
        (self.base / 'calls').write_text('')
        (self.run / 'wayland-kit').touch()
        result = self.invoke(mode='gui')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('waydroid session stop', self.calls())

    def test_stop_and_release_failures_never_start_competing_session(self):
        before = self.complete_device()
        for mode in ['gui-stop-fail', 'gui-stop-hang', 'gui-no-release',
                     'gui-stopped-lie', 'gui-bus-failure']:
            with self.subTest(mode=mode):
                for name in ['session', 'stop-attempted']:
                    (self.base / name).unlink(missing_ok=True)
                (self.base / 'calls').write_text('')
                result = self.invoke('--wait', '1', mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('transfer', result.stderr)
                self.assertIn('retry', result.stderr)
                self.assertNotIn('enable --now', self.calls())
                self.assertNotIn('ADB serial:', result.stdout)
                self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_after_stop_startup_failures_have_recovery_without_false_ready(self):
        before = self.complete_device()
        for mode in ['gui-start-race', 'gui-start-fail', 'gui-start-unconfirmed', 'gui-start-foreign',
                     'gui-unauthorized', 'gui-properties-failed', 'gui-adb-owner-race', 'gui-boot-timeout']:
            with self.subTest(mode=mode):
                (self.base / 'session').unlink(missing_ok=True)
                (self.base / 'calls').write_text('')
                result = self.invoke('--wait', '1', mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('transfer', result.stderr)
                self.assertIn('journalctl', result.stderr)
                self.assertIn('waydroid session stop', self.calls())
                if mode.startswith('gui-start') and mode != 'gui-start-race':
                    self.assertNotIn('adb devices', self.calls())
                if mode == 'gui-start-race':
                    self.assertNotIn('systemctl --user enable --now kit-waydroid.service', self.calls())
                self.assertNotIn('ADB serial:', result.stdout)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
        (self.base / 'calls').write_text('')
        self.assert_ok(self.invoke())  # repair/retry after the last ADB failure
        self.assertNotIn('waydroid session stop', self.calls())
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_graphical_prerequisite_and_data_failures_preserve_gui(self):
        before = self.complete_device()
        (self.bin / 'adb').unlink()
        # Available packages are checked read-only before any GUI stop.
        apt_cache = self.bin / 'apt-cache'
        apt_cache.write_text('#!/bin/sh\nexit 1\n')
        self.assertNotEqual(self.invoke(mode='gui').returncode, 0)
        self.assertNotIn('waydroid session stop', self.calls())
        self.assertNotIn('sudo ', self.calls())
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        (self.state / 'images/vendor.img').write_bytes(b'incomplete')
        result = self.invoke(mode='gui')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Preserve data', result.stderr)
        self.assertNotIn('waydroid session stop', self.calls())

    def test_stopped_and_foreign_sessions_are_not_stopped(self):
        self.complete_device()
        self.assert_ok(self.invoke())
        self.assertNotIn('waydroid session stop', self.calls())
        (self.base / 'session').write_text('foreign')
        (self.base / 'calls').write_text('')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('2000', result.stderr)
        self.assertNotIn('waydroid session stop', self.calls())
        self.assertNotIn('sudo ', self.calls())

    def test_unsupported_capabilities_refuse_before_mutation(self):
        for mode, expected in [('no-binder', 'Binder'), ('not-linux', 'Linux'), ('no-arch', 'architecture')]:
            with self.subTest(mode=mode):
                result = self.invoke(mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertNotIn('sudo ', self.calls())
                self.assertFalse((self.home / '.local').exists())

    def test_setup_repeat_two_directories_and_preserve_data_keys(self):
        self.assert_ok(self.invoke())
        self.assertIn('https://ota.waydro.id/system', self.calls())
        self.assertIn('https://ota.waydro.id/vendor', self.calls())
        data = self.state / 'data/sentinel'
        data.parent.mkdir()
        data.write_text('keep data')
        key = self.home / '.android/adbkey'
        key.parent.mkdir()
        key.write_text('keep key')
        units = self.home / '.config/systemd/user'
        before = {p.name: p.read_bytes() for p in units.iterdir()}
        self.assertIn('Environment="XDG_DATA_HOME=' + self.env['XDG_DATA_HOME'] + '"',
                      (units / 'kit-waydroid.service').read_text())
        self.assert_ok(self.invoke())
        self.assertEqual(sum(line.startswith('waydroid init ') for line in self.calls().splitlines()), 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in units.iterdir()})
        self.assertEqual(data.read_text(), 'keep data')
        self.assertEqual(key.read_text(), 'keep key')
        for name in ['repo-one', 'unrelated-repo']:
            repo = self.base / name
            repo.mkdir()
            (self.base / 'calls').write_text('')
            result = self.invoke('--status', cwd=repo)
            self.assert_ok(result)
            self.assertIn('ADB serial: 192.0.2.8:5555', result.stdout)
            self.assertIn('Android: 13', result.stdout)
            self.assertIn('ABI: x86_64', result.stdout)
            self.assertNotIn('sudo ', self.calls())

    def test_interrupted_init_preserves_valid_image_and_checks_false_success(self):
        self.state.mkdir(parents=True)
        images = self.state / 'images'
        images.mkdir()
        image = images / 'system.img'
        image.write_bytes(b'\0' * 1080 + b'\x53\xef' + b'\0' * 1024)
        before = image.read_bytes()
        (self.state / 'waydroid.cfg').write_text('[waydroid]\nimages_path = ' + str(images) + '\nsystem_datetime = 1\nvendor_datetime = 1\n')
        result = self.invoke(mode='false-init')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('initialization incomplete', result.stderr)
        config = (self.state / 'waydroid.cfg').read_text()
        self.assertIn('system_datetime = 1', config)
        self.assertIn('vendor_datetime = 0', config)
        self.assertNotIn('enable --now', self.calls())
        # Interruption after init made empty overlay scaffolding is still safe.
        (self.state / 'overlay_rw/system').mkdir(parents=True)
        self.assert_ok(self.invoke())
        self.assertEqual(image.read_bytes(), before)
        self.assertNotIn('--force', self.calls())

    def test_revalidate_initialization_after_acquiring_setup_lock(self):
        flock = self.bin / 'flock'
        flock.unlink()
        flock.write_text(FAKE)
        flock.chmod(0o755)
        self.assert_ok(self.invoke(mode='peer-completed'))
        self.assertNotIn('waydroid init ', self.calls())
        self.assertEqual((self.state / 'overlay_rw/system/sentinel').read_text(), 'keep overlay')

    @unittest.skipIf(os.geteuid() == 0, 'root can read mode-000 directories')
    def test_unreadable_overlay_is_not_treated_as_empty_scaffolding(self):
        private = self.state / 'overlay_rw/system/private'
        private.mkdir(parents=True)
        (private / 'sentinel').write_text('keep overlay')
        private.chmod(0)
        self.addCleanup(private.chmod, 0o700)
        result = self.invoke('--check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot safely read existing initialization', result.stderr)
        self.assertNotIn('sudo ', self.calls())

    def test_property_query_failure_names_repair_without_ready_report(self):
        (self.base / 'session').write_text('managed')
        result = self.invoke('--status', mode='properties-failed')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Android properties unavailable', result.stderr)
        self.assertIn('--status', result.stderr)
        self.assertNotIn('ADB serial:', result.stdout)

    def test_status_never_activates_an_absent_manager(self):
        result = self.invoke('--status', '--wait', '1', mode='manager-absent')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('waydroid status', self.calls())
        self.assertNotIn('sudo ', self.calls())
        self.assertNotIn('enable --now', self.calls())
        self.assertNotIn('ADB serial:', result.stdout)

    def test_status_distinguishes_failure_states_and_delayed_dhcp(self):
        (self.base / 'session').write_text('managed')
        for mode, expected in [('no-ip', 'No container IP'), ('unauthorized', 'authorization pending'), ('boot-timeout', 'Android boot timeout')]:
            with self.subTest(mode=mode):
                result = self.invoke('--status', '--wait', '1', mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertNotIn('ADB serial:', result.stdout)
        (self.base / 'ip-count').unlink()
        self.assert_ok(self.invoke('--status', '--wait', '4', mode='slow-ip'))

    def test_missing_packages_checked_before_install(self):
        (self.bin / 'waydroid').unlink()
        result = self.invoke('--check', mode='no-package')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('repositories', result.stderr)
        self.assertNotIn('sudo ', self.calls())
        self.assertFalse((self.home / '.local').exists())
        self.assert_ok(self.invoke())
        self.assertIn('apt-get install -y waydroid', self.calls())

    def test_dnf_android_tools_mapping_and_admission(self):
        (self.bin / 'apt-get').unlink()
        (self.bin / 'adb').unlink()
        dnf = self.bin / 'dnf'
        dnf.write_text(FAKE)
        dnf.chmod(0o755)
        result = self.invoke('--check', mode='no-package')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cached DNF package android-tools', result.stderr)
        self.assertNotIn('sudo ', self.calls())
        self.assert_ok(self.invoke())
        self.assertIn('dnf install -y android-tools', self.calls())

    def test_foreign_unit_and_damaged_data_refuse_before_sudo(self):
        unit = self.home / '.config/systemd/user/kit-waydroid.service'
        unit.parent.mkdir(parents=True)
        unit.write_text('foreign unit')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Foreign', result.stderr)
        self.assertNotIn('sudo ', self.calls())
        unit.unlink()
        (self.state / 'data').mkdir(parents=True)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Preserve data', result.stderr)
        self.assertNotIn('sudo ', self.calls())

    def test_user_supervisor_exits_for_systemd_retry_on_session_failure(self):
        result = self.invoke('--session')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('systemd will retry', result.stderr)
        self.assertIn('waydroid session start', self.calls())
        self.assertNotIn('sudo ', self.calls())

    def test_stop_is_unprivileged_and_preserves_data(self):
        self.state.mkdir(parents=True)
        sentinel = self.state / 'data'
        sentinel.write_text('keep')
        self.assert_ok(self.invoke('--stop'))
        self.assertIn('systemctl --user disable --now kit-waydroid.service', self.calls())
        self.assertNotIn('sudo ', self.calls())
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_unknown_option_and_help_are_write_free(self):
        self.assert_ok(self.invoke('--help'))
        self.assertNotEqual(self.invoke('--bad').returncode, 0)
        self.assertEqual(self.calls(), '')


if __name__ == '__main__':
    unittest.main()
