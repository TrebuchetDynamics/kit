#!/usr/bin/env python3
"""Read-only GitHub and local deployment inventory for /unblock all."""
import argparse
import json
from pathlib import Path
import re
import sys

# Reuse the verified scheduler/config and live invocation binding of status all.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'orbi/scripts'))
from orbi_control import Context, ControlError, MIN_PYTHON, host_status_snapshot

OPEN_STATES = {'ai-blocked', 'ai-fix-needed', 'ai-decision', 'ai-in-progress', 'ai-pr-opened'}
CLOSED_STATES = OPEN_STATES | {'ai-ready', 'ai-planning', 'ai-awaiting-merge', 'ai-merged',
                               'ai-needs-detail', 'ai-paused'}
REPO_NAME = re.compile(r'[a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+')
READ_FIX = 'verify gh authentication and repository read access, then retry the inventory'


def read_gh(ctx, args, *, no_checks=False):
    try:
        env = dict(ctx.env, GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1', GH_TELEMETRY='false')
        proc = ctx.run(['gh', *args], env=env, allow_failure=True)
    except ControlError as exc:
        raise ValueError(f'{exc.message}; {exc.fix}') from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError(f'could not read gh {args[0]} output') from exc
    if no_checks and proc.returncode == 1 and not proc.stdout.strip() and re.fullmatch(
            r"no (?:required )?checks reported on the '.+' branch", proc.stderr.strip()):
        return []
    if proc.returncode:
        raise ValueError(f'gh {args[0]} exited {proc.returncode}')
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise ValueError(f'gh {args[0]} returned invalid JSON') from exc


def pages(ctx, repo, endpoint):
    data = read_gh(ctx, ['api', f'repos/{repo}/{endpoint}', '--hostname', 'github.com',
                         '--method', 'GET', '--paginate', '--slurp'])
    if not isinstance(data, list) or any(not isinstance(p, list) or
            not all(isinstance(row, dict) for row in p) for p in data):
        raise ValueError('gh api returned invalid paginated data')
    return [row for page in data for row in page]


def comment_record(body, kind):
    match = re.search(r'<!-- orbi:' + kind + r':v1\s+(.*?)\s*-->', body, re.S)
    if match is None:
        return None
    data = json.loads(match[1])
    if not isinstance(data, dict) or (kind != 'answer' and data.get('schema') != 1):
        raise ValueError('invalid marker schema')
    return data


def issue_markers(comments):
    failure, question, newest_question = None, None, False
    answered = set()
    # GitHub lists issue comments in ascending ID order, across page boundaries.
    for comment in reversed(comments):
        body = comment['body']
        if failure is None and (record := comment_record(body, 'failure')) is not None:
            failure = {key: record[key] for key in ('reason_code', 'action_code')}
            if not all(isinstance(code, str) and code for code in failure.values()):
                raise ValueError('invalid failure codes')
        if not newest_question:
            if (answer := comment_record(body, 'answer')) is not None:
                if (answer['action'] in ('accept', 'decline', 'cancel')
                        and isinstance(answer['q'], str)):
                    answered.add(answer['q'])
            if (record := comment_record(body, 'question')) is not None:
                newest_question = True
                asked = record['question']
                if asked['id'] not in answered:
                    question = {key: asked[key] for key in ('id', 'question')}
                    question['recommended_option'] = next((option for option in asked.get('options', [])
                                                           if option.get('recommended') is True), None)
        if failure is not None and newest_question:
            break
    return failure, question


def issue_number(row):
    number = row['number']
    if type(number) is not int or number < 1:
        raise ValueError('invalid issue or PR number')
    return number


def issues(ctx, repo, state, live, uncertain, errors):
    items = {}
    try:
        for row in pages(ctx, repo, f'issues?state={state}&per_page=100'):
            if 'pull_request' in row:  # REST treats PRs as issues too.
                continue
            labels = {label['name'] for label in row['labels']}
            if state == 'open':
                selected = labels & OPEN_STATES or ('ai-planning' in labels and 'ai-epic' not in labels)
            else:
                selected = labels & CLOSED_STATES
            if selected:
                number = issue_number(row)
                items[number] = {'number': number, 'url': row['html_url'], 'title': row['title'],
                                 'labels': sorted(labels)}
    except ValueError as exc:
        errors.append(f'{state} issues: {exc}')
        return None
    except (KeyError, TypeError):
        errors.append(f'{state} issues: invalid GitHub issue data')
        return None
    result = [items[n] for n in sorted(items)]
    if state == 'open':
        for item in result:
            number = item['number']
            item.update(failure=None, open_question=None,
                        live_local_worker=True if number in live else None if uncertain else False)
            try:
                comments = pages(ctx, repo, f'issues/{number}/comments?per_page=100')
            except ValueError as exc:
                errors.append(f'issue #{number} comments: {exc}')
                continue
            try:
                item['failure'], item['open_question'] = issue_markers(comments)
            except (ValueError, KeyError, TypeError, AttributeError):
                errors.append(f'issue #{number}: invalid Orbi marker or comment data')
    return result


def required_checks(ctx, number, repo):
    checks = read_gh(ctx, ['pr', 'checks', str(number), '--repo', f'github.com/{repo}',
                           '--required', '--json', 'name,state,bucket,link'], no_checks=True)
    checks = sorted(({key: row[key] for key in ('name', 'state', 'bucket', 'link')} for row in checks),
                    key=lambda row: (row['name'], row['link'], row['state'], row['bucket']))
    buckets = {row['bucket'] for row in checks}
    if buckets - {'pass', 'fail', 'pending', 'skipping', 'cancel'}:
        raise ValueError('gh pr checks returned an invalid bucket')
    result = ('fail' if buckets & {'fail', 'cancel'} else 'pending' if 'pending' in buckets
              else 'pass' if checks else 'not_reported')
    return {'result': result, 'checks': checks}


def pull_requests(ctx, repo, errors):
    try:
        rows = {issue_number(row): row for row in pages(ctx, repo, 'pulls?state=open&per_page=100')}
    except ValueError as exc:
        errors.append(f'open PRs: {exc}')
        return None
    except KeyError:
        errors.append('open PRs: missing GitHub pull request number')
        return None
    items = []
    for number, row in sorted(rows.items()):
        try:
            item = {'number': number, 'url': row['html_url'], 'head': row['head']['ref'],
                    'head_sha': row['head']['sha'], 'mergeability': 'UNKNOWN',
                    'required_checks': {'result': 'unknown', 'checks': []}}
        except (KeyError, TypeError):
            errors.append(f'PR #{number}: invalid GitHub pull request data')
            continue
        items.append(item)
        try:
            checks = required_checks(ctx, number, repo)
        except ValueError as exc:
            checks = None
            errors.append(f'PR #{number} required checks: {exc}')
        except (KeyError, TypeError):
            checks = None
            errors.append(f'PR #{number}: invalid required check data')
        # gh pr checks does not return a commit SHA. Discard the result if the
        # head moved between the initial listing and this readback.
        try:
            view = read_gh(ctx, ['pr', 'view', str(number), '--repo', f'github.com/{repo}',
                                 '--json', 'state,headRefName,headRefOid,mergeable'])
            if view['state'] != 'OPEN':
                items.pop()
                errors.append(f'PR #{number}: no longer open during inventory')
                continue
            changed = view['headRefOid'] != item['head_sha'] or view['headRefName'] != item['head']
            item.update(head=view['headRefName'], head_sha=view['headRefOid'], mergeability=view['mergeable'])
            if changed:
                errors.append(f'PR #{number}: head changed during inventory; retry to refresh checks')
            elif checks is not None:
                item['required_checks'] = checks
        except ValueError as exc:
            errors.append(f'PR #{number} head/mergeability: {exc}')
        except (KeyError, TypeError):
            errors.append(f'PR #{number}: invalid head/mergeability data')
    return items


def inventory(ctx):
    host, deployments = host_status_snapshot(ctx)
    local = host['coverage']
    repos, live, uncertain = {}, {}, set()
    global_uncertain = local['state'] != 'ok'
    for config, deployment in deployments.items():
        for name in deployment.get('repos', []):
            if not REPO_NAME.fullmatch(name):
                local['state'] = 'partial'
                local['problems'].append({'manager': None, 'reason': f'invalid source_repos entry in {config}',
                                          'fix': 'repair the deployment config before retrying'})
                continue
            repos.setdefault(name.lower(), [])
    for row in host['rows']:
        worker = row['worker']
        names = {name.lower() for name in row.get('repos', [])} & repos.keys()
        for repo in names:
            repos[repo].append({key: row[key] for key in ('manager', 'unit', 'kind', 'state', 'scheduler')}
                               | {'config': row['binding']['config'], 'worker_state': worker['state'],
                                  'timer_state': row.get('timer_state')})
            issue = worker.get('issue')
            if worker['state'] == 'running' and issue:
                if issue['url'].lower() == f"https://github.com/{repo}/issues/{issue['number']}":
                    live.setdefault(repo, set()).add(issue['number'])
        if row['kind'] == 'runner' and worker['state'] not in {'running', 'idle'} and row['scheduler'] != 'unloaded':
            uncertain.update(names)
            global_uncertain |= not names
    sheets = []
    for repo, rows in sorted(repos.items()):
        errors = []
        opened = issues(ctx, repo, 'open', live.get(repo, ()), global_uncertain or repo in uncertain, errors)
        closed = issues(ctx, repo, 'closed', (), False, errors)
        prs = pull_requests(ctx, repo, errors)
        sheets.append({'repo': repo, 'deployments': sorted(rows, key=lambda row: (
            row['config'], row['manager'] or '', row['unit'] or '')), 'open_issues': opened,
            'closed_issues': closed, 'open_prs': prs, 'errors': errors})
    return {'schema_version': 1, 'local_coverage': local, 'repositories': sheets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='print JSON (the default)')
    parser.parse_args()
    ctx = Context(noninteractive=True)
    if sys.version_info < MIN_PYTHON or ctx.platform not in ('linux', 'darwin'):
        parser.error('inventory requires Python 3.11+ on Linux or macOS')
    document = inventory(ctx)
    print(json.dumps(document, indent=2, sort_keys=True))
    failed = False
    if document['local_coverage']['state'] != 'ok':
        failed = True
        print('Local deployment coverage is partial; see local_coverage.problems for repairs.', file=sys.stderr)
    for sheet in document['repositories']:
        for error in sheet['errors']:
            failed = True
            print(f"{sheet['repo']}: {error}; {READ_FIX}.", file=sys.stderr)
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
