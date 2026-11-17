#!/usr/bin/env python3
"""Opt-in live Pi planning smoke; never called by the offline test inventory.

Run --help first. Evidence stays in a new private directory outside the checkout.
A passing receipt checks observed reads, a final response and unchanged fixture
bytes; inspect the response and shell trace for semantic adherence separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_pi(command, project, env, stdout, stderr, timeout):
    """A timed-out invocation must not outlive the fixture's final snapshot."""
    process = subprocess.Popen(command, cwd=project, env=env, stdout=stdout, stderr=stderr,
                               start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def snapshot(root):
    result = {}
    for path in sorted(root.rglob('*')):
        key = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[key] = ('link', os.readlink(path))
        elif path.is_file():
            result[key] = ('file', path.stat().st_mode, hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            result[key] = ('directory', path.stat().st_mode)
    return result


def inspect_trace(path, project, kit, skill):
    """Check observable smoke boundaries, not the quality of the model's answer."""
    records = [json.loads(line) for line in path.read_text().split('\n') if line.strip()]
    failures, reads, starts, final = [], set(), {}, ''
    for item in records:
        if not isinstance(item, dict):
            raise ValueError('JSONL records must be objects')
        kind = item.get('type')
        if kind == 'tool_execution_start':
            starts[item.get('toolCallId')] = item
            if item.get('toolName') in ('write', 'edit'):
                failures.append('planning attempted a write/edit tool')
        elif kind == 'tool_execution_end':
            start = starts.pop(item.get('toolCallId'), {})
            if start.get('toolName') == 'read' and item.get('isError') is False:
                raw = start.get('args', {}).get('path')
                if isinstance(raw, str):
                    reads.add((project / raw).resolve())
        elif kind == 'message_end' and item.get('message', {}).get('role') == 'assistant':
            message = item['message']
            # A partial/intermediate response never substitutes for the final one.
            final = ''.join(part.get('text', '') for part in message.get('content', [])
                            if part.get('type') == 'text') if message.get('stopReason') == 'stop' else ''
            if message.get('stopReason') in ('error', 'aborted', 'length'):
                failures.append('assistant did not finish normally')
    if not final.strip():
        failures.append('no completed assistant response (exit 0 alone is not success)')
    for required in (project / 'README.md', kit / 'skills' / skill / 'SKILL.md'):
        if required.resolve() not in reads:
            failures.append(f'missing successful read: {required.relative_to(project) if required.is_relative_to(project) else "canonical skill"}')
    return failures, final


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--skill', choices=('plan-with-me', 'plan-for-me'), default='plan-with-me')
    parser.add_argument('--thinking', default='low')
    parser.add_argument('--pi', default='pi-bolt', help='Pi executable (default: pi-bolt on PATH)')
    parser.add_argument('--kit-root', type=Path, default=ROOT, help='checkout or unpacked Pi package')
    parser.add_argument('--agent-dir', type=Path, default=Path(os.environ.get('PI_CODING_AGENT_DIR', Path.home() / '.pi/agent')))
    parser.add_argument('--output-dir', type=Path, required=True, help='new evidence directory outside Kit')
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args(argv)
    if os.name != 'posix':
        parser.error('the live smoke requires POSIX process-group cleanup (Linux/macOS)')
    kit, output, auth_home = args.kit_root.resolve(), args.output_dir.resolve(), args.agent_dir.resolve()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if any(output.is_relative_to(path) for path in (ROOT, kit, auth_home)):
        parser.error('--output-dir must be outside Kit and the existing agent directory')
    adapter = kit / 'adapters/skills' / args.skill
    if not (adapter / 'SKILL.md').is_file():
        parser.error('Kit portable skill is missing')
    if output.exists():
        parser.error('--output-dir must be new; existing evidence is never overwritten')
    output.mkdir(mode=0o700, parents=True)
    project, agent = output / 'project', output / 'agent'
    project.mkdir(); agent.mkdir()
    (project / 'README.md').write_text('# Line counter\n\nA proposed CLI counts nonempty lines in one UTF-8 file.\n'
                                     'Input path and whitespace-only line handling are undecided.\n'
                                     'No implementation exists.\n')
    (agent / 'settings.json').write_text('{}\n')
    # Reuse stored authentication/catalog without copying credentials or settings.
    for name in ('auth.json', 'models.json'):
        source = auth_home / name
        if source.is_file():
            (agent / name).symlink_to(source)
    failures, final, code = [], '', None
    try:
        subprocess.run(['git', '-c', 'init.templateDir=', 'init', '--quiet', str(project)], check=True,
                       capture_output=True, timeout=10)
        before = snapshot(project)
        request = ('questions only: read README.md and help me clarify the line counter. Ask exactly one '
                   'question about an unresolved requirement, then stop.' if args.skill == 'plan-with-me' else
                   'read-only: read README.md and recommend a bounded plan for the line counter. '
                   'Make compatible assumptions and identify them; do not interview me.')
        request += ' Do not write files, publish issues, implement, commit, push or start services.'
        command = [args.pi, '--provider', args.provider, '--model', args.model, '--thinking', args.thinking,
                   '--mode', 'json', '--no-session', '--no-extensions', '--no-mcp', '--no-skills',
                   '--skill', str(adapter), '--no-prompt-templates', '--no-themes', '--no-context-files',
                   '--tools', 'read,bash,edit,write', '-p', f'/skill:{args.skill} {request}']
        env = dict(os.environ, PI_CODING_AGENT_DIR=str(agent), PI_OFFLINE='1', PI_TELEMETRY='0')
        try:
            with (output / 'session.jsonl').open('w') as stdout, (output / 'stderr.txt').open('w') as stderr:
                code = run_pi(command, project, env, stdout, stderr, args.timeout)
        finally:
            if snapshot(project) != before:
                failures.append('fixture files changed')
        if code != 0:
            failures.append(f'Pi exited with {code}')
        observed, final = inspect_trace(output / 'session.jsonl', project, kit, args.skill)
        failures.extend(observed)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        failures.append(f'{type(exc).__name__}; inspect private evidence')
    receipt = {'ok': not failures, 'skill': args.skill, 'provider': args.provider, 'model': args.model,
               'kit_root': str(kit), 'pi_exit': code, 'failures': failures,
               'semantic_review': 'required: inspect final.txt and session.jsonl; not automated'}
    (output / 'final.txt').write_text(final + '\n')
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'ok': receipt['ok'], 'evidence': str(output), 'failures': failures}))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
