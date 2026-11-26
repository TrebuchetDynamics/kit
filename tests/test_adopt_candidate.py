"""Run the Unblock handoff CLI against real disposable Git and fixture GitHub."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/unblock/scripts/adopt_candidate.py'
REPO = 'Owner/Repo'
BRANCH = 'orbi/Owner-Repo-issue-17'
MARKER = '<!-- orbi:run=abcd1234 -->'
PR = 'https://github.com/Owner/Repo/pull/42'

FAKE_GH = '''
import json, os, sys
from pathlib import Path
import subprocess

path = Path(os.environ['FIXTURE'])
data = json.loads(path.read_text())
args = sys.argv[1:]

def option(name):
    return args[args.index(name) + 1]

if args[:2] == ['issue', 'view']:
    assert args[2] == '17' and option('--repo') == 'github.com/Owner/Repo'
    results = {
        'state': 'OPEN', 'title': 'Repair delivery',
        'labels': [{'name': x} for x in data['labels']],
        'blockedBy': data.get('blockedBy', {'nodes': [], 'totalCount': 0}),
    }
    print(json.dumps({x: results[x] for x in option('--json').split(',')}))
elif args[:2] == ['api', 'repos/Owner/Repo/issues/17/comments']:
    assert '--paginate' in args and '--slurp' in args
    print(json.dumps([[comment] for comment in data['comments']]))
elif args[:1] == ['api']:
    assert args[1].startswith('repos/Owner/Repo/collaborators/') and args[1].endswith('/permission')
    author = args[1].split('/')[-2]
    print(json.dumps({'permission': data['permissions'][author]}))
elif args[:2] == ['pr', 'list']:
    assert option('--repo') == 'github.com/Owner/Repo'
    assert option('--head') == data['branch'] and option('--state') == 'open'
    print(json.dumps(data['prs']))
elif args[:2] == ['pr', 'create']:
    branch = option('--head')
    assert branch == data['branch'] and not data['prs']
    assert option('--repo') == 'github.com/Owner/Repo'
    sha = subprocess.check_output([os.environ['REAL_GIT'], '--git-dir', os.environ['ORIGIN'],
                                   'rev-parse', f'refs/heads/{branch}'], text=True, timeout=5).strip()
    data['prs'].append({'url': data['url'], 'body': option('--body'), 'baseRefName': option('--base'),
                        'headRefName': branch, 'headRefOid': sha, 'isCrossRepository': False,
                        'isDraft': False})
    data['writes'].append('pr create')
    path.write_text(json.dumps(data))
    print(data['url'])
elif args[:2] == ['issue', 'edit']:
    assert args[2] == '17' and option('--repo') == 'github.com/Owner/Repo'
    assert data['prs'] and option('--remove-label') == 'ai-blocked'
    assert option('--add-label') == 'delivery-ready'
    data['labels'].remove('ai-blocked')
    data['labels'].append('delivery-ready')
    data['writes'].append('issue edit')
    path.write_text(json.dumps(data))
else:
    raise AssertionError(args)
'''


class AdoptCandidateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.checkout = root / 'checkout'
        self.checkout.mkdir()
        self.origin = root / 'origin.git'
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        self.fixture = root / 'github.json'
        self.config = root / 'orbi.toml'
        self.config.touch()
        self.real_git = shutil.which('git')
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                        FIXTURE=str(self.fixture), REAL_GIT=self.real_git, ORIGIN=str(self.origin),
                        CONFIG=str(self.config), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        self.executable(bin_dir / 'gh', FAKE_GH)
        self.executable(bin_dir / 'orbi', '''
import json, os, sys
from pathlib import Path
assert sys.argv[1:] == ['status', '--config', os.environ['CONFIG'], '--repo', 'Owner/Repo', '--issue', '17']
data = json.loads(Path(os.environ['FIXTURE']).read_text())
print(f"slots: {data['slots']}/2\\nsource: Owner/Repo")
''')
        # Stub only remote identity; use actual Git transport and history for the fixture.
        self.executable(bin_dir / 'git', '''
import json, os, sys, subprocess
from pathlib import Path
if sys.argv[1:3] == ['remote', 'get-url']:
    print('https://github.com/Owner/Repo.git')
else:
    # Simulate another publisher creating a fast-forwardable branch after
    # the helper checked it but before Git contacts the remote.
    race = json.loads(Path(os.environ['FIXTURE']).read_text()).get('race_tip')
    if 'push' in sys.argv[1:] and race:
        subprocess.run([os.environ['REAL_GIT'], '--git-dir', os.environ['ORIGIN'],
                        'update-ref', 'refs/heads/orbi/Owner-Repo-issue-17', race], check=True, timeout=5)
    os.execv(os.environ['REAL_GIT'], ['git', *sys.argv[1:]])
''')
        self.set_data(labels=['ai-blocked', 'bug'], slots=0, writes=[], prs=[], branch=BRANCH, url=PR,
                      permissions={'maintainer': 'write', 'outsider': 'read'}, comments=[
                          {'user': {'login': 'maintainer'}, 'body': MARKER},
                          {'user': {'login': 'outsider'}, 'body': '<!-- orbi:run=deadbeef -->'},
                      ])
        self.git('init', '--bare', str(self.origin))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('remote', 'add', 'origin', str(self.origin))
        self.git('commit', '--allow-empty', '-m', 'initial')
        self.git('switch', '-c', 'owner-candidate')
        self.candidate = self.commit('fix.txt')
        self.git('switch', 'main')
        self.base = self.commit('base.txt')
        self.git('push', 'origin', 'main')
        self.git('switch', 'owner-candidate')
        (self.checkout / 'fix.txt').write_text('local uncommitted edit')

    def executable(self, path, body):
        path.write_text(f'#!{sys.executable}\n{body}')
        path.chmod(0o755)

    def data(self):
        return json.loads(self.fixture.read_text())

    def set_data(self, **changes):
        data = self.data() if self.fixture.exists() else {}
        self.fixture.write_text(json.dumps(data | changes))

    def git(self, *args):
        result = subprocess.run([self.real_git, *args], cwd=self.checkout, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, name):
        (self.checkout / name).write_text(name)
        self.git('add', name)
        self.git('commit', '-m', name)
        return self.git('rev-parse', 'HEAD')

    def adopt(self, candidate=None):
        return subprocess.run([sys.executable, str(SCRIPT), REPO, '17', candidate or self.candidate,
                               '--config', str(self.config), '--base', 'main',
                               '--dispatch-label', 'delivery-ready'],
                              cwd=self.checkout, env=self.env, capture_output=True, text=True, timeout=30)

    def delivery_tip(self):
        return self.git('ls-remote', '--refs', 'origin', f'refs/heads/{BRANCH}').split('\t')[0]

    def test_merges_and_verifies_same_repository_pr_before_requeue(self):
        result = self.adopt()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(PR, result.stdout)
        data = self.data()
        self.assertEqual(data['writes'], ['pr create', 'issue edit'])
        self.assertCountEqual(data['labels'], ['bug', 'delivery-ready'])
        (pr,) = data['prs']
        self.assertEqual(pr['body'].splitlines()[:2], [MARKER, 'Fixes #17'])
        self.assertRegex(pr['body'], r'Fixes #?17(?!\d)')  # Orbi pr_verification, not GitHub's Closes
        self.assertEqual((pr['headRefName'], pr['baseRefName'], pr['url']), (BRANCH, 'main', PR))
        self.assertEqual(pr['headRefOid'], self.delivery_tip())
        self.assertEqual(self.git('show', '-s', '--format=%P', self.delivery_tip()).split(),
                         [self.candidate, self.base])
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.candidate)
        self.assertEqual((self.checkout / 'fix.txt').read_text(), 'local uncommitted edit')
        self.assertNotIn(str(self.checkout / '.worktrees'), self.git('worktree', 'list', '--porcelain'))

    def test_refuses_even_fast_forwardable_remote_branch_with_different_commit(self):
        self.git('push', 'origin', f'{self.base}:refs/heads/{BRANCH}')
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already points to', result.stderr)
        self.assertEqual(self.delivery_tip(), self.base)
        self.assertEqual(self.data()['writes'], [])

    def test_concurrent_branch_creation_is_not_fast_forwarded(self):
        self.set_data(race_tip=self.base)
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stale info', result.stderr)
        self.assertEqual(self.delivery_tip(), self.base)
        self.assertEqual(self.data()['writes'], [])

    def test_refuses_live_deployment_even_with_blocked_label(self):
        self.set_data(slots=1)
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('live worker', result.stderr)
        self.assertEqual(self.delivery_tip(), '')
        self.assertEqual(self.data()['writes'], [])

    def test_refuses_unfinished_trusted_start_even_when_local_slots_are_empty(self):
        comments = self.data()['comments']
        comments.append({'user': {'login': 'maintainer'}, 'body': f'{MARKER}\n<!-- orbi:comment=started -->'})
        self.set_data(comments=comments)
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('possible live worker', result.stderr)
        self.assertEqual(self.delivery_tip(), '')
        self.assertEqual(self.data()['writes'], [])

    def test_conflict_leaves_only_the_scratch_worktree_for_repair(self):
        self.git('switch', '--discard-changes', 'main')
        (self.checkout / 'fix.txt').write_text('conflicting base change')
        self.git('add', 'fix.txt')
        self.git('commit', '-m', 'conflicting base')
        self.git('push', 'origin', 'main')
        self.git('switch', 'owner-candidate')
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CONFLICT', result.stderr)
        self.assertIn('Prepared worktree retained', result.stderr)
        self.assertEqual(self.delivery_tip(), '')
        self.assertEqual(self.data()['writes'], [])
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no'), '')
        (scratch,) = (self.checkout / '.worktrees').iterdir()
        self.assertEqual(self.git('-C', str(scratch), 'diff', '--name-only', '--diff-filter=U'), 'fix.txt')

    def test_refuses_when_only_marker_is_untrusted(self):
        self.set_data(permissions={'maintainer': 'read', 'outsider': 'read'})
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No trusted Orbi run marker', result.stderr)
        self.assertEqual(self.delivery_tip(), '')
        self.assertEqual(self.data()['writes'], [])

    def test_existing_compatible_pr_is_reused_without_rewrite(self):
        self.assertEqual(self.adopt().returncode, 0)
        published = self.delivery_tip()
        self.set_data(labels=['ai-blocked', 'bug'], writes=[])
        result = self.adopt(published)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(PR, result.stdout)
        self.assertEqual(self.data()['writes'], ['issue edit'])

    def test_missing_original_scene_pr_does_not_create_replacement(self):
        comments = self.data()['comments']
        scene = {'schema': 1, 'run_id': 'abcd1234', 'base_branch': 'main', 'base_sha': self.base,
                 'external': '', 'review_round': 0, 'pr_url': PR}
        comments.append({'user': {'login': 'maintainer'},
                         'body': f'{MARKER}\n<!-- orbi:scene:v1 {json.dumps(scene)} -->'})
        self.set_data(comments=comments)
        result = self.adopt()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('same PR URL', result.stderr)
        self.assertEqual(self.delivery_tip(), '')
        self.assertEqual(self.data()['writes'], [])

    def test_incompatible_pr_is_not_edited_or_requeued(self):
        self.assertEqual(self.adopt().returncode, 0)
        (pr,) = self.data()['prs']
        pr['body'] = f'{MARKER}\nCloses #17'
        self.set_data(labels=['ai-blocked'], writes=[], prs=[pr])
        result = self.adopt(self.delivery_tip())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Fixes #17', result.stderr)
        self.assertEqual(self.data()['writes'], [])


if __name__ == '__main__':
    unittest.main()
