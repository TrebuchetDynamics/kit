# Skill evals

Three tiers, each with a different claim.

| Tier | Check | Evidence |
| --- | --- | --- |
| 1 | Structure | `tests/test_skill_standard.py` checks descriptions, boundaries, rationalizations, red flags and the Definition of Done link. |
| 2 | Routing and description | `tests/test_workflow_commands.py` checks the pilot commands are named by `ask-kit` and their descriptions are distinct summaries. |
| 3 | Recorded trace | `scripts/skill_trace_eval.py` grades a JSON trace against `evals/tier3/<skill>.json`. |

## Tier 3 trace format

A trace is one JSON object:

```json
{
  "name": "ponytail-review-pass",
  "skill": "ponytail-review",
  "model": "fixture",
  "note": "Synthetic fixture; not a model run.",
  "events": [
    {"type": "read", "path": "src/parser.py"},
    {"type": "final", "text": "No findings; review does not authorize delivery."}
  ]
}
```

Event types: `read`, `write`, `edit`, `command`, `assistant`, `final`. An `assistant`
event records nonfinal, user-visible assistant chat in `text`, in observation order;
it is not thinking, a user message or tool output. `final` stays distinct. A `tool` event with
`tool: "read"`, `"write"` or `"edit"` is the same as that event type. A `tool`
event with `tool: "bash"` or `"shell"` and a command is a `command` event. Paths
may be top-level or under `args.path`; commands may be top-level or under
`args.command`. Paths are repository-relative strings. Commands include the exact
command text and, when known for that invocation, an exit code. An absent `exit`
is unknown, not zero.

## Tier 3 spec format

A spec names required and forbidden events:

```json
{
  "skill": "ponytail-review",
  "tier": 3,
  "description": "Review trace: read the change, report, never edit or commit.",
  "require": [
    {"event": "read", "path": "*"},
    {"event": "final"}
  ],
  "forbid": [
    {"event": "write", "path": "*"},
    {"event": "command", "command": "git (commit|push)"}
  ]
}
```

`path` is an fnmatch pattern. `command` is a regular expression. `exit` is the
required exit code when present and only valid with `command`. `contains` is valid
with `assistant` or `final` and matches case-insensitive substrings; use it sparingly
because exact wording is a weak oracle. A `require` clause may include `before_first`,
one non-nested event matcher using the same fields. The required event must occur
strictly before the first matching boundary event; a missing boundary also fails.
Only fields in that boundary matcher constrain it (omit `exit` to include failed
and unknown-status attempts). Other requirements remain unordered. Unknown keys
and fields on the wrong event type are refused.

A review spec forbids `write` and `edit`. A git command check must account for global
options such as `git -C . commit`, not only `git commit`; see
`evals/tier3/ponytail-review.json`.

## Planning pilot: writable fresh helper publication

`plan-for-me.json` and `plan-with-me.json` select one **writable-fresh-publication
pilot**: investigate, show the user a plan preview **before the first publication
attempt**, successfully invoke `scripts/github_issues.py` with an actual `--apply`
argument, then give a final receipt. The synthetic `*-pass.json` fixtures record a
nonfinal `assistant` event with `text` containing `Plan preview`, followed by the
supported command:

```sh
python3 scripts/github_issues.py --repo OWNER/REPO --batch /tmp/batch.json --apply
```

This is recorded data, not a command to run as part of an eval. The publisher's
`--help` and [handoff contract](../skills/shared/PLAN-HANDOFF.md) own the actual
interface. The pilot matches the bare helper path or a `python`/`python3` invocation
(optionally `-B`), with unquoted arguments before `--apply`, and requires recorded
exit 0. Preview-only, failed or missing-status publication cannot satisfy persistence.
Help invocations (`-h`, `--help` or its argparse abbreviations) do not count, even
when combined with `--apply`: they exit 0 without publishing.
The preview requirement uses `before_first` with the same helper command matcher,
without an exit constraint. Thus a failed or unknown-status early apply followed by
a preview and successful retry still fails. Missing or post-apply previews, a preview
only in the final answer, and helper dry-run output without an assistant preview all
fail. A helper dry-run before the chat preview is allowed; it is not publication.
This is evidence for the existing [Plan preview](../skills/shared/PLAN-HANDOFF.md#plan-preview)
visibility contract, not a new workflow stage or mandatory approval turn. No local
plan/spec write is required when the issue owns all decisions. A final event is
required, but the grader does not semantically validate its receipt text.

`Plan preview` is a bounded lexical signal, not a semantic quality check: the grader
does not establish completeness, accuracy, useful decomposition or actual display
on a user's device. Record real visible assistant text; do not annotate thinking or
tool output as `assistant` to manufacture a pass.

This is **not every valid planning outcome**. Questions-only, unsaved, no-write, explicit no-dispatch,
reuse-without-republication, coordinator-return, publication failure and direct-API
publication are different scenarios, not failed skill adherence merely because they
do not satisfy this selected pilot. Select matching evidence rather than applying
these two specs as universal planning gates. The
[retained recovery specimens](../tests/fixtures/planning/README.md) from #33 are
inert inputs and expected outcomes, not traces evaluated by this pilot.

### Known pilot artifact layout

The guards enumerate repository-relative artifact owners, not universal filename or
extension roles in arbitrary consumer repositories. Both `write` and `edit`, including
the documented tool wrappers, are refused for:

- `tasks/**` (retired local queue; historical reads remain allowed).
- `src/**`, `scripts/**`, `tests/**`, `adapters/**`, `skills/**` (including executable
  `SKILL.md` and shared instructions), and `.github/**` (CI).
- `.claude-plugin/**`, `.codex-plugin/**`, `.agents/plugins/**`, `plugins/**`.
- Root `__init__.py`, `install.sh`, `install-plugins.sh`, `install-skills.sh`,
  `AGENTS.md`, `CLAUDE.md`, `package.json`, `plugin.yaml`, `requirements-test.txt`.
- Named lockfiles `package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`,
  `yarn.lock`, `uv.lock`.

Authorized `docs/` plan-owner writes and transient publication input such as
`/tmp/batch.json` remain allowed; scratch is not a replacement backlog. Recorded
`git commit`/`push` (including global options) are refused. Selected activation
patterns cover `systemctl start/restart/enable`, `launchctl load/bootstrap/kickstart/
start/enable`, `orbi start/setup/install-units` and retired `pi-autowork
start/run/resume/restart`; read-only status and history commands remain allowed.

These regex/path checks do not infer arbitrary shell effects, normalize every path
alias or prove universal write safety. A successful synthetic helper event is **not
a remote receipt**: it does not prove issue contents, dependency correctness,
readiness order or actual model choices. The publisher's own focused tests and
actual readback own publication guarantees. This pilot does not execute commands,
call GitHub or establish live model adherence, Orbi pickup or delivery.

## Push delivery pilot

`push.json` checks recorded inspection and a receipt that separates local commits,
incoming landed changes, pending URLs/reasons, selected/final SHAs, checks, remote
inclusion and remaining local sync. `push-pass.json` represents merged remote-only
work through a non-`origin`, non-`main` verified upstream. Other `push-*.json`
fixtures cover a passing-but-owned open PR, API rate-limit/unknown inventory,
upstream advance with an open PR becoming merged, closed-unmerged/failed/unknown
work, equivalence and a read-only audit. All commands and API responses are inert
recorded examples; no fixture contacts GitHub or mutates Git.

The focused tests use existing `require`/`forbid` clauses for scenario receipts and
the fixture's held PR head. They apply the read-only review clauses to the push
audit; delivery's general spec cannot condition on a mode. Planning/review clauses
also reject fetch, including Git global-option forms. These are bounded lexical
checks, not semantic candidate selection, ancestry validation, a shell sandbox,
state ordering or model adherence. Neither a receipt's words nor exit 0 establishes
live delivery. Source-backed inventory and independent PR review remain necessary.

## Run

```sh
python3 scripts/skill_trace_eval.py evals/tier3/ponytail-review.json \
  evals/tier3/traces/ponytail-review-pass.json
```

For a real Pi session, capture JSONL with `pi --mode json -p ...`, then convert it:

```sh
python3 scripts/pi_trace_to_eval.py --skill ponytail-review \
  --name ponytail-review-live session.jsonl -o /tmp/ponytail-review-live.json
python3 scripts/skill_trace_eval.py evals/tier3/ponytail-review.json \
  /tmp/ponytail-review-live.json
```

The converter removes heredoc bodies, maps read-only `cat`/`head`/`tail`/`sed`/
`git show`/`git diff`/`git log` commands to read events, preserves earlier assistant
text as ordered `assistant` events, and keeps the last assistant text as `final`.
Only assistant `message_end` text parts become chat evidence; thinking, user messages
and tool output do not. Tool attempts are positioned at `tool_execution_start`, not
completion, so a preview during an in-flight apply is already late. Missing results
remain unknown-status attempts. Conversion does not execute recorded commands or
modify the source trace. Keep live traces and credentials outside Git.

The converter attributes `exit` only to an unambiguously single simple shell
invocation with an integer tool exit code (not a boolean). Missing or malformed
status stays unknown. Compound commands (`CHECK || true`, `CHECK; true`,
`false && CHECK`), pipelines, multiline input, grouping, `[[ ... ]]` conditionals,
heredocs, substitutions, redirections and shell wrappers such as `sh -c 'CHECK'`
do not provide per-command exit evidence. Quoted operator-like text may
conservatively be ambiguous too.
Their command events retain valid numeric tool status as `aggregate_exit_code`,
provenance only: the grader does not use it to satisfy an `exit=0` requirement.
Command text remains available to forbidden-action matching, even when it may have
failed or never executed.

To collect reliable success evidence, capture verification as a separate simple
tool invocation with its own result. Do not rewrite a historic trace or guess an
inner command's exit from a successful wrapper. An aggregate-success trace without
separate per-invocation evidence yields a missing required-success event.

Exit 0 means the trace satisfies the spec. Exit 1 means a required event is missing,
its `before_first` constraint failed, or a forbidden action occurred. For example,
`missing required before first` identifies missing/late preview evidence. Recover by
capturing a real pre-publication chat preview in a new authorized run and reconverting;
never reorder or fabricate evidence in a historic trace. Exit 2 means the JSON or
spec is malformed.

## Opt-in local planning smoke (Pi)

Use `scripts/planning_smoke.py` to exercise one portable planning skill with a real
configured model in a disposable Git repository. This is a paid/live operation,
separate from `scripts/check.py` and CI. Select an authenticated provider/model;
the helper does not log in or install a host:

```sh
python3 scripts/planning_smoke.py --provider PROVIDER_ID --model MODEL_ID \
  --output-dir /tmp/kit-plan-with-me-evidence
python3 scripts/planning_smoke.py --provider PROVIDER_ID --model MODEL_ID \
  --skill plan-for-me --output-dir /tmp/kit-plan-for-me-evidence
```

Each output directory must be new and outside Kit and the existing Pi agent
configuration. It is created private (mode 0700) and retains the fixture, JSONL,
stderr, final response and receipt, including on failure. Keep it outside Git.
This helper supports Linux/macOS (POSIX process groups). `--timeout SECONDS`
bounds each Pi invocation and kills its process group before the final fixture
snapshot on timeout. `--pi PATH` selects an executable;
`--agent-dir PATH` selects the existing authentication/catalog source.
The temporary agent directory uses empty settings and links existing `auth.json`
and `models.json` when present; credentials are not copied. Normal Pi authentication
may refresh the linked auth file. Packages, extensions, MCP, context discovery,
themes and prompt templates are disabled; the selected portable skill is loaded
explicitly. Existing profile settings and services are not changed. This is
resource isolation, not a filesystem or network sandbox.

The smoke leaves read/bash/edit/write tools available, asks for no local or GitHub
writes and compares all fixture files/directories, including `.git`, afterward.
It requires successful reads of the README and canonical skill, a normally completed
nonempty assistant response, and no write/edit tool attempts. Exit 0 without a
response fails. Inspect `final.txt` and shell commands in `session.jsonl` yourself:
Plan With Me should ask one relevant unresolved question; Plan For Me should give
a bounded plan with explicit assumptions, without an interview. The automated
receipt does not judge answer quality, arbitrary shell side effects or remote state.
It is not the writable-publication Tier 3 pilot or Orbi qualification.

To test shipped contents rather than checkout files, run `npm pack --ignore-scripts
--pack-destination /tmp/CHOSEN_DIRECTORY`, unpack that archive outside the checkout,
and pass `--kit-root /path/to/unpacked/package`. Both fixture and loaded skill paths
remain recorded privately. No installed Pi package or real project is modified.

The helper uses native `/skill:plan-with-me` or `/skill:plan-for-me` expansion.
In Pi 1.5.2, the short extension command in `--mode json -p` was observed to exit 0
with only a session header: its fire-and-forget `sendUserMessage` is not awaited by
single-shot command dispatch. See the pinned [command dispatch](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/agent-session.ts)
and [print lifecycle](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/modes/print-mode.ts).
This limitation does not establish the behavior of interactive/RPC commands or other
Pi releases. Do not count the process exit alone as model evidence.

## Limits

The checked-in traces are synthetic fixtures. A passing fixture proves the grader and
spec work, not that a live agent followed the skill. Tier 3 does not execute trace
content, call a model or prove delivery. Collect live traces from the host session,
redact secrets and store them outside Git; grade them with the same command.

Heredoc-example exclusion, command splitting, read derivation and regex matching are
limited lexical approximations, not complete shell interpretation, a shell audit or
a security sandbox. They can miss actions or match text that was not executed;
conservative exit attribution does not make grading semantically complete or
qualify live skill behavior.
