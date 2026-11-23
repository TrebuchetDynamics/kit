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
import os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
root = Path(os.environ['FIXTURE'])
with (root / 'calls').open('a') as f:
    f.write(name + ' ' + ' '.join(args) + '\n')
mode = os.environ.get('MODE', '')
if name == 'id':
    print('1000' if '-u' in args else 'tester')
elif name == 'uname':
    print(('Darwin' if mode == 'not-linux' else 'Linux') if '-s' in args else ('riscv64' if mode == 'no-arch' else 'x86_64'))
elif name == 'modinfo':
    sys.exit(1 if mode == 'no-binder' else 0)
elif name == 'sudo':
    if args == ['-v'] or args == ['-n', '-v']: sys.exit(0)
    if args[0] == '--': args = args[1:]
    os.execvp(args[0], args)
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
        # Real init consumes the pre-init rendering config into base properties.
        cfg = (state / 'waydroid.cfg').read_text()
        assert 'ro.hardware.egl = swiftshader' in cfg
        (state / 'waydroid_base.prop').write_text('ro.hardware.egl=swiftshader\n')
        (state / 'rootfs').mkdir(exist_ok=True)
        (state / 'lxc/waydroid').mkdir(parents=True, exist_ok=True)
        (state / 'lxc/waydroid/config').write_text('lxc config')
        (state / 'waydroid.cfg').write_text('[waydroid]\nimages_path = ' + str(state / 'images') + '\nsystem_datetime = 1\nvendor_datetime = 1\n')
    elif args[0] == 'status':
        count = root / 'ip-count'
        n = int(count.read_text()) if count.exists() else 0
        count.write_text(str(n+1))
        ip = 'UNKNOWN' if mode == 'no-ip' or (mode == 'slow-ip' and n == 0) else '192.0.2.8'
        print('Session:\tRUNNING\nContainer:\tRUNNING\nIP address:\t' + ip)
elif name == 'adb':
    if args[0] == 'devices':
        state = 'unauthorized' if mode == 'unauthorized' else 'device'
        print('List of devices attached\n192.0.2.8:5555\t' + state)
    elif 'getprop' in args:
        key = args[-1]
        print({'sys.boot_completed': '0' if mode == 'boot-timeout' else '1', 'ro.build.version.release': '13', 'ro.product.cpu.abi': 'x86_64'}[key])
elif name == 'weston':
    if '--help' in args:
        print('--backend --use-pixman headless --socket --no-config')
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
        for name in ['id', 'uname', 'sudo', 'systemctl', 'loginctl', 'waydroid', 'weston', 'adb', 'modinfo', 'apt-cache', 'apt-get']:
            p = self.bin / name
            p.write_text(FAKE)
            p.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_DATA_HOME=str(self.home / '.local/share'), XDG_RUNTIME_DIR=str(self.run),
                        PATH=str(self.bin), FIXTURE=str(self.base))

    def invoke(self, *args, mode='', cwd=None):
        result = subprocess.run([str(self.script), *args], env=dict(self.env, MODE=mode),
                                cwd=cwd or self.base, text=True, capture_output=True, timeout=15)
        return result

    def calls(self):
        p = self.base / 'calls'
        return p.read_text() if p.exists() else ''

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_status_distinguishes_failure_states_and_delayed_dhcp(self):
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
