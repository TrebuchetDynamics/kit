"""install.sh hands every argument to the component menu unchanged."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def entry(self, name, target):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo with spaces'
            (repo / 'scripts').mkdir(parents=True)
            Path(repo, target).write_text('import sys,json; print(json.dumps(sys.argv[1:])); sys.exit(7)')
            shutil.copy2(ROOT / name, repo / name)
            return subprocess.run(['bash', str(repo / name), '--only', 'tx', '--skip', '/tmp/value with spaces'],
                                  cwd=tmp, capture_output=True, text=True)

    def test_install_sh_runs_the_menu_with_every_flag(self):
        result = self.entry('install.sh', 'scripts/install_menu.py')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn('"/tmp/value with spaces"', result.stdout)

if __name__ == '__main__':
    unittest.main()
