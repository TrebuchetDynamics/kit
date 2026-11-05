#!/usr/bin/env python3
"""Run the tests a push can affect, before the push; the full suite stays CI's job.

    git push                      # the hook runs `scripts/affected_tests.py --base <pushed-from> --run`
    python3 scripts/pre_push_check.py --install   # write or chain the hook into .git/hooks/pre-push
    KIT_PRE_PUSH=0 git push       # skip the tests this once (so does `git push --no-verify`)

The core contracts (docs check, task-store validation) run first, in seconds: the selector
leaves documents to them. Git hands a pre-push hook one line per ref: local ref, local sha, remote ref, remote sha.
The base of the change is the remote's current sha when this repository knows it, else
the merge-base with origin/main (the selector's own default). Deleted refs and refs with
nothing new are skipped. The selection follows the working tree, as the selector does, so
uncommitted edits are tested too; a change to the check, CI or packaging selects the whole
suite, and that is the one case a push takes minutes.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ZERO = '0' * 40
MARKER = 'pre_push_check.py'
HOOK = '''#!/bin/sh
# Installed with --install: the affected tests run before a push; the whole suite is CI's job.
input=$(cat)
printf '%s\\n' "$input" | python3 "$(git rev-parse --show-toplevel)/scripts/pre_push_check.py" "$@"
'''


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True)


def known(sha):
    return git('cat-file', '-e', f'{sha}^{{commit}}').returncode == 0


def pushed_bases(lines, known=None):
    """The distinct bases of the refs being pushed, in order; None stands for the selector's
    default (a ref the remote does not have yet, or a remote sha this clone has not fetched)."""
    known = globals()['known'] if known is None else known
    bases = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha, _remote_ref, remote_sha = parts
        if local_sha == ZERO or local_sha == remote_sha:
            continue  # a deletion, or nothing new
        base = remote_sha if remote_sha != ZERO and known(remote_sha) else None
        if base not in bases:
            bases.append(base)
    return bases


HOOK_VARIABLES = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_EDITOR', 'GIT_EXEC_PATH', 'GIT_PREFIX',
                  'GIT_REFLOG_ACTION', 'GIT_PUSH_OPTION_COUNT')


def test_environment(env=os.environ):
    """The environment the tests see: Git exports GIT_EDITOR=true, GIT_EXEC_PATH and GIT_PREFIX to a
    hook, and GIT_EDITOR=true alone failed eight planning tests whose fixtures expect a plain shell.
    GIT_CONFIG_* entries stay (scripts/check.py handles the runner's push guard itself).
    TMPDIR gets a real directory: three suites read it with os.environ['TMPDIR'] and an interactive
    shell that never set it made them fail as if the tree were red, which invites --no-verify."""
    kept = {key: value for key, value in env.items()
            if key not in HOOK_VARIABLES and not key.startswith('GIT_PUSH_OPTION_')}
    kept.setdefault('TMPDIR', tempfile.gettempdir())
    return kept


def run_core():
    """The checker's cheap core contracts (docs check, task-store validation): they cover the
    documents the selector leaves to them, in a few seconds."""
    import runpy
    core = runpy.run_path(str(ROOT / 'scripts/check.py'))['affected_core']
    print('pre-push: core contracts (docs check, task-store validation)', flush=True)
    return 0 if core(ROOT) else 1


def run_affected(base):
    command = [sys.executable, str(ROOT / 'scripts/affected_tests.py'), '--run', *(['--base', base] if base else [])]
    print('pre-push: ' + ' '.join(command[1:]), flush=True)
    return subprocess.run(command, cwd=ROOT, env=test_environment()).returncode


def install(hooks):
    """Write the hook, or chain into one that already exists, once."""
    path = hooks / 'pre-push'
    if path.exists() and MARKER in path.read_text():
        print(f'{path}: already installed')
        return 0
    if path.exists():
        existing = path.read_text()
        if existing.startswith('#!/bin/sh\nexec '):
            # A one-line exec hook (the private-terms check, for example) keeps running first.
            chained = existing.replace('#!/bin/sh\nexec ', '#!/bin/sh\ninput=$(cat)\nprintf \'%s\\n\' "$input" | ', 1).rstrip('\n')
            chained += ' || exit 1\nprintf \'%s\\n\' "$input" | python3 "$(git rev-parse --show-toplevel)/scripts/pre_push_check.py" "$@"\n'
            path.write_text(chained)
        else:
            print(f'{path} exists and is not a one-line exec hook; add this line to it yourself:\n'
                  '  printf \'%s\\n\' "$input" | python3 "$(git rev-parse --show-toplevel)/scripts/pre_push_check.py" "$@"',
                  file=sys.stderr)
            return 1
    else:
        path.write_text(HOOK)
    path.chmod(0o755)
    print(f'{path}: installed')
    return 0


def main(argv=None, stdin=None, run=run_affected, core=run_core):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['--install']:
        hooks = Path(git('rev-parse', '--git-path', 'hooks').stdout.strip() or '.git/hooks')
        return install(hooks if hooks.is_absolute() else ROOT / hooks)
    if os.environ.get('KIT_PRE_PUSH', '1') == '0':
        print('pre-push: KIT_PRE_PUSH=0, affected tests skipped; CI runs the whole suite', flush=True)
        return 0
    lines = (sys.stdin if stdin is None else stdin).read().splitlines()
    bases = pushed_bases(lines)
    if not bases:
        return 0
    if core():
        print('pre-push: a core contract refused this tree; nothing was pushed. Fix it, or leave this one to CI with\n'
              '  git push --no-verify', file=sys.stderr, flush=True)
        return 1
    for base in bases:
        code = run(base)
        if code:
            print('pre-push: affected tests failed; nothing was pushed. Fix them, or leave this one to CI with\n'
                  '  git push --no-verify', file=sys.stderr, flush=True)
            return code
    return 0


if __name__ == '__main__':
    sys.exit(main())
