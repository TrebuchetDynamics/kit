#!/usr/bin/env python3
"""Publish a blocked, unowned Orbi candidate from its local Git checkout."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote


RUN_MARKER = re.compile(r'<!-- orbi:run=[0-9a-f]{8} -->')
COMMENT_KIND = re.compile(r'\A' + RUN_MARKER.pattern + r'\r?\n<!-- orbi:comment=([a-z-]+) -->')
SCENE = re.compile(r'<!--\s*orbi:scene:v1\s+(.*?)-->', re.DOTALL)
EXTERNAL_PR = re.compile(r'<!--\s*orbi:external-pr:(\d+)\s*-->')
BLOCKED = 'ai-blocked'
OWNED = {'ai-in-progress', 'ai-pr-opened', 'ai-fix-needed', 'ai-awaiting-merge'}
HELD = {'ai-planning', 'ai-merged', 'ai-epic', 'ai-needs-detail', 'ai-release', 'ai-content-only', 'ai-ops-only'}


def run(*args, cwd=None, timeout=45):
    result = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, errors='replace', timeout=timeout)
    if result.returncode:
        # Retain Git/gh diagnostics (including merge conflict filenames).
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result.stdout.strip()


def read_issue(args, fields):
    return json.loads(run('gh', 'issue', 'view', str(args.issue), '--repo', f'github.com/{args.repo}',
                          '--json', fields))


def eligible_issue(args):
    issue = read_issue(args, 'state,title,labels,blockedBy,body,closedByPullRequestsReferences')
    labels = {entry['name'] for entry in issue['labels']}
    if labels & (OWNED | {args.dispatch_label}):
        raise ValueError('Issue is already queued or owned; wait for its current delivery.')
    if issue['state'] != 'OPEN' or BLOCKED not in labels or labels & HELD:
        raise ValueError('Expected an open ai-blocked issue with no other lifecycle gate; revisit /unblock diagnosis.')
    blockers = issue['blockedBy']
    if blockers['totalCount'] != len(blockers['nodes']) or any(
        node['state'] != 'CLOSED' for node in blockers['nodes']
    ):
        raise ValueError('Native blockers are open or unreadable; resolve them before requeuing.')
    if external := EXTERNAL_PR.search(issue['body']):
        raise ValueError(f'Issue routes to external PR #{external[1]}; use the existing owner-first repair path.')
    return issue


def require_same_link(issue, url):
    for link in issue['closedByPullRequestsReferences']:
        if link['url'] != url:
            raise ValueError(f'Issue already links to {link["url"]}; reconcile that PR before adopting.')


def require_idle(args):
    # Orbi status exposes local slot occupancy, not a slot-to-issue API.
    status = run('orbi', 'status', '--config', str(args.config), '--repo', args.repo,
                 '--issue', str(args.issue))
    slots = re.findall(r'^slots: (\d+)/(\d+)$', status, re.MULTILINE)
    if f'source: {args.repo}' not in status.splitlines() or len(slots) != 1 or int(slots[0][1]) < 1:
        raise ValueError('Could not confirm deployment ownership; check orbi status on the owning deployment.')
    if int(slots[0][0]):
        raise ValueError('The deployment has a live worker; wait for its slot to clear before adopting.')


def account_name(login):
    return login.removesuffix('[bot]').lower()


def delivery_history(repo, issue, runner_login):
    pages = json.loads(run('gh', 'api', f'repos/{repo}/issues/{issue}/comments', '--hostname',
                           'github.com', '--paginate', '--slurp'))
    permissions, live, markers = {}, set(), []
    scene_url = None
    for page in pages:
        for comment in page:
            body = comment['body']
            found = RUN_MARKER.findall(body)
            if not found:
                continue
            login = comment['user']['login']
            kind = COMMENT_KIND.match(body)
            if login not in permissions:
                try:
                    permission = json.loads(run(
                        'gh', 'api', f'repos/{repo}/collaborators/{quote(login, safe="")}/permission',
                        '--hostname', 'github.com',
                    ))['permission']
                except subprocess.CalledProcessError as exc:
                    if '(HTTP 404)' not in exc.stderr:
                        raise
                    permission = 'none'
                permissions[login] = permission
            account = account_name(login)
            # Orbi trusts writers and the owning runner's own account. The
            # publisher's gh credential need not be the runner's credential.
            trusted = permissions[login] in {'write', 'admin'} or account == runner_login
            if trusted:
                markers.extend(found)
                scenes = SCENE.findall(body)
                if scenes:
                    try:
                        (scene,) = scenes
                        scene_url = json.loads(scene)['pr_url']
                        if not isinstance(scene_url, str) or not scene_url:
                            raise ValueError('invalid PR URL')
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError('Unreadable Orbi scene; reconcile the existing PR before adopting.') from exc
            # A bot on another deployment may not have collaborator permission.
            if kind and (trusted or login.endswith('[bot]')):
                if kind[1] == 'started':
                    live.add(account)
                elif kind[1] in {'failure', 'merged', 'requeued'}:
                    live.discard(account)
    if live:
        raise ValueError('Run history shows a possible live worker; confirm the current attempt ended before adopting.')
    if not markers:
        raise ValueError('No trusted Orbi run marker in issue history; verify the owning runner login or recover the original run evidence.')
    return markers, scene_url


def check_origin(repo):
    allowed = {f'{prefix}{repo}{suffix}'.lower()
               for prefix in ('https://github.com/', 'git@github.com:', 'ssh://git@github.com/')
               for suffix in ('', '.git')}
    for flags in ((), ('--push',)):
        if run('git', 'remote', 'get-url', '--all', *flags, 'origin').lower() not in allowed:
            raise ValueError(f'origin must fetch and push only to github.com/{repo}; use the matching checkout.')


def remote_tip(ref):
    raw = run('git', 'ls-remote', '--refs', 'origin', ref)
    if not raw:
        return None
    oid, name = raw.split('\t')
    if name != ref:
        raise ValueError(f'Unexpected remote ref {name}; expected {ref}.')
    return oid


@contextmanager
def candidate_worktree(commit):
    # Use the canonical checkout even if the candidate lives in a linked worktree.
    first = run('git', 'worktree', 'list', '--porcelain', '-z').split('\0\0', 1)[0].split('\0')
    if 'bare' in first or not first[0].startswith('worktree '):
        raise ValueError('Run from a non-bare candidate checkout.')
    parent = Path(first[0][9:]) / '.worktrees'
    if parent.is_symlink():
        raise ValueError(f'Worktree directory is a symlink: {parent}')
    parent.mkdir(exist_ok=True)
    tree = Path(tempfile.mkdtemp(prefix='unblock-', dir=parent))
    try:
        run('git', 'worktree', 'add', '--detach', str(tree), commit)
        yield tree
    except Exception:
        print(f'Prepared worktree retained at {tree}; inspect it and remote state before retrying.', file=sys.stderr)
        raise
    else:
        try:
            run('git', 'worktree', 'remove', str(tree))
        except (OSError, subprocess.SubprocessError) as exc:
            # Local cleanup must not turn a published, verified handoff into failure.
            print(f'Could not remove scratch worktree {tree}: {getattr(exc, "stderr", None) or exc}', file=sys.stderr)


def open_pr(repo, branch):
    prs = json.loads(run('gh', 'pr', 'list', '--repo', f'github.com/{repo}', '--state', 'open',
                         '--head', branch, '--json',
                         'url,body,baseRefName,headRefName,headRefOid,isCrossRepository,isDraft'))
    if not isinstance(prs, list) or len(prs) > 1:
        raise ValueError(f'Cannot identify one PR on {branch}; reconcile the delivery line with its owner.')
    return prs[0] if prs else None


def verify_pr(pr, args, branch, head, markers, expected_url=None):
    if not pr or (expected_url is not None and pr['url'] != expected_url):
        raise ValueError('Could not read back the same PR URL; inspect the existing delivery before retrying.')
    url = pr['url']
    if (not re.fullmatch(rf'https://github\.com/{re.escape(args.repo)}/pull/[1-9]\d*', url, re.I)
        or pr['isCrossRepository'] is not False or pr['isDraft'] is not False
        or (pr['headRefName'], pr['headRefOid'], pr['baseRefName']) != (branch, head, args.base)):
        raise ValueError(f'{url} does not match the same-repository head/base; reconcile with the owner.')
    if not any(marker in pr['body'] for marker in markers) or not re.search(
        rf'Fixes #?{args.issue}(?!\d)', pr['body']
    ):
        raise ValueError(f'{url} needs a trusted delivery-line marker and Fixes #{args.issue}; reconcile the existing PR.')
    return url


def adopt(args):
    branch = f"orbi/{args.repo.replace('/', '-')}-issue-{args.issue}"
    ref = f'refs/heads/{branch}'
    base_ref = f'refs/heads/{args.base}'
    if base_ref == ref:
        raise ValueError('The base and delivery branch must differ.')
    run('git', 'check-ref-format', base_ref)
    run('git', 'check-ref-format', ref)
    check_origin(args.repo)
    candidate = run('git', 'rev-parse', '--verify', '--end-of-options', f'{args.commit}^{{commit}}')
    eligible_issue(args)
    require_idle(args)
    delivery_history(args.repo, args.issue, args.runner_login)
    existing = remote_tip(ref)
    if existing and existing != candidate:
        raise ValueError(f'Delivery branch {branch} already points to {existing}; reconcile with the owner.')
    with candidate_worktree(candidate) as tree:
        # FETCH_HEAD is per worktree. An empty refmap leaves the deployment's
        # shared remote-tracking refs alone and pins the exact fetched base.
        run('git', 'fetch', '--no-tags', '--refmap=', 'origin', base_ref, cwd=tree)
        base = run('git', 'rev-parse', '--verify', 'FETCH_HEAD', cwd=tree)
        run('git', '-c', 'rerere.enabled=false', 'merge', '--no-edit', '--no-autostash', '--ff', base, cwd=tree)
        head = run('git', 'rev-parse', 'HEAD', cwd=tree)
        if head == base:
            raise ValueError(f'Candidate has no commits outside origin/{args.base}; check the supplied commit.')
        if existing and existing != head:
            raise ValueError(f'Delivery branch {branch} needs a base merge; use the existing owner-first repair path.')
        markers, scene_url = delivery_history(args.repo, args.issue, args.runner_login)
        pr = open_pr(args.repo, branch)
        issue = eligible_issue(args)
        require_same_link(issue, pr['url'] if pr else None)
        require_idle(args)
        if not (pr or scene_url or existing):
            # The empty lease asserts ABSENCE, so this can only create the
            # ref, never force-update (or fast-forward) another writer's tip.
            run('git', '-c', 'remote.origin.mirror=false', 'push', '--no-follow-tags',
                f'--force-with-lease={ref}:', 'origin', f'HEAD:{ref}', cwd=tree, timeout=180)
            markers, scene_url = delivery_history(args.repo, args.issue, args.runner_login)
            pr = open_pr(args.repo, branch)
            issue = eligible_issue(args)
            require_same_link(issue, pr['url'] if pr else None)
            require_idle(args)
        if pr or scene_url:
            url = verify_pr(pr, args, branch, head, markers, expected_url=scene_url)
        else:
            if remote_tip(ref) != head:
                raise ValueError(f'Delivery branch {branch} changed; reconcile with the owner.')
            url = run('gh', 'pr', 'create', '--repo', f'github.com/{args.repo}', '--base', args.base,
                      '--head', branch, '--title', issue['title'], '--body', f'{markers[-1]}\nFixes #{args.issue}')
        print(f'Candidate {head} PR: {url}', flush=True)
        markers, scene_url = delivery_history(args.repo, args.issue, args.runner_login)
        if scene_url and scene_url != url:
            raise ValueError('The trusted scene now names another PR; keep the same PR URL and reconcile ownership.')
        verify_pr(open_pr(args.repo, branch), args, branch, head, markers, expected_url=url)
        require_idle(args)
        if remote_tip(ref) != head:
            raise ValueError(f'Delivery branch {branch} changed; reconcile with the owner.')
        if remote_tip(base_ref) != base:
            raise ValueError(f'origin/{args.base} changed during publication; update and recheck the same PR before requeuing.')
        require_same_link(eligible_issue(args), url)
        run('gh', 'issue', 'edit', str(args.issue), '--repo', f'github.com/{args.repo}',
            '--add-label', args.dispatch_label, '--remove-label', BLOCKED)
        labels = {entry['name'] for entry in read_issue(args, 'labels')['labels']}
        if BLOCKED in labels or not labels & ({args.dispatch_label, 'ai-merged'} | OWNED):
            raise ValueError('Requeue was not confirmed; inspect issue labels and Orbi status before retrying.')
        print(f'Handoff published via {args.dispatch_label}; check Orbi for pickup.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', help='GitHub OWNER/REPO as configured in Orbi')
    parser.add_argument('issue', type=int)
    parser.add_argument('commit', help='Exact local candidate commit to publish')
    parser.add_argument('--config', required=True, type=Path, help='Owning deployment’s Orbi config')
    parser.add_argument('--base', required=True, help='Effective Orbi base branch')
    parser.add_argument('--dispatch-label', required=True, help='Effective Orbi queue label (normally ai-ready)')
    parser.add_argument('--runner-login', type=account_name, help='Verified GitHub login of the owning Orbi credential')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', args.repo) or args.issue < 1:
        parser.error('expected a GitHub OWNER/REPO and positive issue number')
    if args.runner_login is not None and not re.fullmatch(r'[a-z0-9-]+', args.runner_login):
        parser.error('--runner-login must be the owning deployment’s GitHub account login')
    if not args.config.is_file():
        parser.error('--config must name the owning deployment’s configuration file')
    if (not args.dispatch_label.strip() or ',' in args.dispatch_label
        or args.dispatch_label in OWNED | HELD | {BLOCKED, 'ai-human-review'}):
        parser.error('--dispatch-label must be the deployment’s queue label, not a lifecycle gate')
    try:
        adopt(args)
    except subprocess.CalledProcessError as exc:
        detail = '\n'.join(value.strip() for value in (exc.stdout, exc.stderr) if value.strip())
        print(f'Adoption stopped: {exc.cmd[0]} {exc.cmd[1]} failed ({exc.returncode}): {detail}', file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'Adoption stopped: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
