"""Installer restart cannot undo an owner stop during inventory or safe-point wait."""
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi_autowork import command, service


class ConditionalRestartTests(unittest.TestCase):
    def test_stopped_after_inventory_is_not_revived_or_reauthorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = dict(env_dir=tmp, state_root=tmp)
            marker = service.stop_marker(Path(tmp) / 'repo.env')
            marker.write_text('owner stopped it')
            with patch.object(command, 'service_state', return_value='installed'), \
                    patch.object(command, 'systemctl', return_value=Mock(returncode=0)) as ctl:
                code, text = command.restart(paths, 'repo', tmp, stop_workers=True, if_active=True)
            self.assertEqual(code, 0)
            ctl.assert_not_called()
            self.assertEqual(marker.read_text(), 'owner stopped it')
            self.assertIn('explicit stop or pause retained', text)

    def test_stop_during_safe_point_wait_remains_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = dict(env_dir=tmp, state_root=tmp)
            marker = service.stop_marker(Path(tmp) / 'repo.env')
            @contextmanager
            def wait(*args):
                marker.write_text('stopped while waiting')
                yield True, ''
            with patch.object(command, 'service_state', return_value='active'), \
                    patch.object(service, '_restart_when_idle', side_effect=wait) as safe_point, \
                    patch.object(command, 'systemctl', return_value=Mock(returncode=0)) as ctl:
                code, _ = command.restart(paths, 'repo', tmp, stop_workers=True, if_active=True)
            self.assertEqual(code, 0)
            safe_point.assert_called_once()
            ctl.assert_not_called()
            self.assertEqual(marker.read_text(), 'stopped while waiting')

    def test_inactive_without_stop_marker_uses_systemd_active_only_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = dict(env_dir=tmp, state_root=tmp)
            with patch.object(command, 'service_state', return_value='installed'), \
                    patch.object(command, 'systemctl', return_value=Mock(returncode=0)) as ctl:
                code, _ = command.restart(paths, 'repo', tmp, stop_workers=True, if_active=True)
            self.assertEqual(code, 0)
            ctl.assert_called_once_with(paths, 'try-restart', 'pi-autowork@repo.service', quiet=False)

    def test_explicit_restart_keeps_existing_start_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = dict(env_dir=tmp)
            marker = service.stop_marker(Path(tmp) / 'repo.env')
            marker.write_text('stopped')
            with patch.object(command, 'systemctl', return_value=Mock(returncode=0)) as ctl:
                self.assertEqual(command.restart(paths, 'repo', tmp, stop_workers=True, now=True)[0], 0)
            self.assertFalse(marker.exists())
            ctl.assert_called_once_with(paths, 'restart', 'pi-autowork@repo.service', quiet=False)
            parsed = command.parser().parse_args(['restart', '--stop-workers', '--if-active', 'repo'])
            self.assertTrue(parsed.if_active)


if __name__ == '__main__':
    unittest.main()
