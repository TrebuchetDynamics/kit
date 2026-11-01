#!/usr/bin/env python3
"""Inventory the repository's worktrees and merge the finished ones into the base branch.

    python3 worktree_sweep.py REPO [--base main] [--apply] [--remove] [--json]

Every registered worktree is classified before anything is merged:

    merged         HEAD is already contained in the base branch
    unmerged-clean commits are not on the base branch and the tree is clean
    unmerged-dirty commits are not on the base branch and the tree has changes
    detached       no branch is checked out, so it is a release or review checkout
    locked         Git holds a worktree lock

`--apply` merges the `unmerged-clean` ones one at a time with a merge commit, never a
rebase, a force, a stash or a reset. A conflict aborts that merge and the sweep
continues with the next worktree. `unmerged-dirty`, `detached` and `locked` worktrees
are reported and left exactly as they are: this tool never commits, discards or moves
another writer's uncommitted work.

Worktrees are merged oldest commit first, so work that others build on lands early. A
worktree whose Git metadata changed within `--idle-minutes` (default 5) is treated as
live and skipped, because another session may still be writing there.

`--remove` hands each worktree that became merged and clean to the repository's
worktree_closeout.py, which removes it only after its own safety checks.

Exit status is 0 when the sweep completed, 1 when it refused to start or a merge
failed, and 2 for a usage error.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

CLASSES = ('merged', 'unmerged-clean', 'unmerged-dirty', 'detached', 'locked', 'prunable')


def git(repo, *args, check=True):
    done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if check and done.returncode:
        raise RuntimeError(done.stderr.strip() or f'git {" ".join(args)} failed')
    return done.stdout.strip()


def worktrees(repo):
    """Parse `git worktree list --porcelain` into records, canonical checkout first."""
    records, current = [], {}
    for line in git(repo, 'worktree', 'list', '--porcelain').splitlines():
        if not line.strip():
            if current:
                records.append(current)
            current = {}
            continue
        key, _, value = line.partition(' ')
        if key == 'worktree':
            current['path'] = value
        elif key == 'HEAD':
            current['head'] = value
        elif key == 'branch':
            current['branch'] = value.removeprefix('refs/heads/')
        else:
            current.setdefault('flags', []).append(key)
    if current:
        records.append(current)
    return records


def classify(repo, record, base):
    path = Path(record['path'])
    flags = set(record.get('flags', []))
    entry = {'path': str(path), 'branch': record.get('branch', ''),
             'head': record.get('head', ''), 'ahead': 0, 'behind': 0,
             'modified': 0, 'untracked': 0, 'state': '', 'note': ''}
    entry['idle_minutes'] = None
    for candidate in (path / '.git', path):
        # A linked worktree's .git is a file; its Git directory holds the index and refs.
        target = candidate
        if target.is_file():
            text = target.read_text(errors='replace').strip()
            if text.startswith('gitdir:'):
                target = Path(text.split(':', 1)[1].strip())
                if not target.is_absolute():
                    target = (path / target).resolve()
        if target.exists():
            age = time.time() - target.stat().st_mtime
            entry['idle_minutes'] = round(age / 60, 1)
            break
    if 'locked' in flags or any(f.startswith('locked') for f in flags):
        entry['state'] = 'locked'
        return entry
    if not record.get('branch'):
        entry['state'] = 'detached'
        return entry
    counts = git(path, 'rev-list', '--left-right', '--count', f'{base}...HEAD')
    # --left-right prints commits only in base first, then commits only in HEAD.
    entry['behind'], entry['ahead'] = (int(n) for n in counts.split())
    status = git(path, 'status', '--porcelain', '--untracked-files=normal', check=False)
    for line in status.splitlines():
        if line.startswith('??'):
            entry['untracked'] += 1
        elif line.strip():
            entry['modified'] += 1
    dirty = entry['modified'] or entry['untracked']
    if entry['ahead'] == 0:
        entry['state'] = 'merged'
    else:
        entry['state'] = 'unmerged-dirty' if dirty else 'unmerged-clean'
    return entry


def preflight(repo, base):
    """Refuse to merge into a branch the canonical checkout is not on, or over local edits."""
    branch = git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    if branch != base:
        raise SystemExit(f'refusing: the canonical checkout is on {branch!r}, not {base!r}. '
                         f'Check out {base} first; this sweep never moves your HEAD.')
    if git(repo, 'status', '--porcelain', '--untracked-files=no'):
        raise SystemExit('refusing: the canonical checkout has uncommitted changes. '
                         'Commit or set them aside first; the sweep never stashes.')
    if (Path(repo) / '.git' / 'MERGE_HEAD').exists():
        raise SystemExit('refusing: a merge is already in progress in the canonical checkout.')


def merge(repo, entry, base):
    """Merge one worktree commit into the base branch, aborting that merge on conflict."""
    result = subprocess.run(['git', '-C', str(repo), 'merge', '--no-ff', '--no-edit',
                             entry['head']], capture_output=True, text=True)
    if result.returncode == 0:
        entry['result'] = 'merged'
        return True
    if (Path(repo) / '.git' / 'MERGE_HEAD').exists():
        subprocess.run(['git', '-C', str(repo), 'merge', '--abort'], capture_output=True, text=True)
        entry['result'] = 'conflict'
    else:
        entry['result'] = 'failed'
    entry['note'] = (result.stderr.strip() or result.stdout.strip()).splitlines()[-1][:200]
    return False


def closeouts(repo, entries, closer):
    if closer is None:
        return
    for entry in entries:
        if entry.get('result') != 'merged' and entry['state'] != 'merged':
            continue
        done = subprocess.run([sys.executable, str(closer), str(repo),
                               '--worktree', entry['path'], '--apply'],
                              capture_output=True, text=True)
        entry['closed'] = 'removed' if done.returncode == 0 else 'kept'
        if done.returncode:
            entry['note'] = (done.stdout.strip() or done.stderr.strip()).splitlines()[-1][:200]


def report(entries, as_json):
    if as_json:
        print(json.dumps(entries, indent=2))
        return
    width = max((len(e['path']) for e in entries), default=10)
    print(f'{"worktree":{width}}  {"branch":28} {"ahead":>5} {"dirty":>5}  state')
    for e in entries:
        dirty = e['modified'] + e['untracked']
        branch = (e['branch'] or '(detached)')[:28]
        extra = f"  -> {e['result']}" if e.get('result') else ''
        print(f'{e["path"]:{width}}  {branch:28} {e["ahead"]:>5} {dirty:>5}  {e["state"]}{extra}')
        if e['note']:
            print(f'{"":{width}}  {e["note"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('repo', type=Path, help='canonical checkout')
    parser.add_argument('--base', default='', help='base branch (default: the checked-out branch)')
    parser.add_argument('--apply', action='store_true', help='merge unmerged-clean worktrees')
    parser.add_argument('--remove', action='store_true',
                        help='remove worktrees that are merged and clean, through worktree_closeout.py')
    parser.add_argument('--closeout', type=Path, default=None,
                        help='path to worktree_closeout.py (default: the repository copy)')
    parser.add_argument('--json', action='store_true', help='print the inventory as JSON')
    parser.add_argument('--idle-minutes', type=int, default=5,
                        help='skip a worktree whose Git metadata changed this recently (0 disables)')
    args = parser.parse_args()

    repo = args.repo.resolve()
    base = args.base or git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    preflight(repo, base)

    records = worktrees(repo)
    entries = [classify(repo, record, base) for record in records[1:]]  # skip the canonical one
    closer = args.closeout or (repo / 'pi-autowork/engine/worktree_closeout.py')
    closer = closer if args.remove and closer.is_file() else None

    failed = 0
    if args.apply:
        candidates = [entry for entry in entries if entry['state'] == 'unmerged-clean']
        candidates.sort(key=lambda entry: git(repo, 'log', '-1', '--format=%ct', entry['head']))
        for entry in candidates:
            if (args.idle_minutes and entry['idle_minutes'] is not None
                    and entry['idle_minutes'] < args.idle_minutes):
                entry['result'] = 'skipped'
                entry['note'] = f'active within {args.idle_minutes} min; merge it when it is idle'
                continue
            if not merge(repo, entry, base):
                failed += 1
    if closer:
        closeouts(repo, entries, closer)

    report(entries, args.json)
    counts = {}
    for entry in entries:
        counts[entry['state']] = counts.get(entry['state'], 0) + 1
    summary = ', '.join(f'{count} {state}' for state, count in sorted(counts.items()))
    print(f'\n{len(entries)} worktree(s): {summary or "none"}')
    if args.apply:
        merged = sum(1 for e in entries if e.get('result') == 'merged')
        print(f'Merged {merged} into {base}; {failed} merge failure(s); '
              f'{sum(1 for e in entries if e["state"] == "unmerged-dirty")} kept dirty.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
