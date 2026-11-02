# Skill evals

Three tiers, each with a different claim.

| Tier | Check | Evidence |
| --- | --- | --- |
| 1 | Structure | `tests/test_skill_standard.py` checks descriptions, boundaries, rationalizations, red flags and the Definition of Done link. |
| 2 | Routing and description | `tests/test_workflow_commands.py` checks the pilot commands are named by `ask-autowork` and their descriptions are distinct summaries. |
| 3 | Recorded trace | `scripts/skill_trace_eval.py` grades a JSON trace against `evals/tier3/<skill>.json`. |

## Tier 3 trace format

A trace is one JSON object:

```json
{
  "name": "autowork-pass",
  "skill": "autowork",
  "model": "fixture",
  "note": "Synthetic fixture; not a model run.",
  "events": [
    {"type": "tool", "tool": "read", "path": "tasks/items/T-1.md"},
    {"type": "write", "path": "src/parser.py"},
    {"type": "command", "command": "python3 scripts/check.py tests/test_parser.py", "exit": 0},
    {"type": "final", "text": "Task T-1 checked and closed with evidence."}
  ]
}
```

Event types: `read`, `write`, `edit`, `command`, `final`. A `tool` event with
`tool: "read"`, `"write"` or `"edit"` is the same as that event type. A `tool`
event with `tool: "bash"` or `"shell"` and a command is a `command` event. Paths
may be top-level or under `args.path`; commands may be top-level or under
`args.command`. Paths are repository-relative strings. Commands include the exact
command and exit code.

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
required exit code when present and only valid with `command`. `contains` is only
valid with `final`; use it sparingly because exact wording is a weak oracle. Unknown
keys and fields on the wrong event type are refused.

A review spec forbids `write` and `edit`. A git command check must account for global
options such as `git -C . commit`, not only `git commit`; see
`evals/tier3/ponytail-review.json`.

## Run

```sh
python3 scripts/skill_trace_eval.py evals/tier3/autowork.json \
  evals/tier3/traces/autowork-pass.json
```

For a real Pi session, capture JSONL with `pi --mode json -p ...`, then convert it:

```sh
python3 scripts/pi_trace_to_eval.py --skill ponytail-review \
  --name ponytail-review-live session.jsonl -o /tmp/ponytail-review-live.json
python3 scripts/skill_trace_eval.py evals/tier3/ponytail-review.json \
  /tmp/ponytail-review-live.json
```

The converter removes heredoc bodies, maps read-only `cat`/`head`/`tail`/`sed`/
`git show`/`git diff`/`git log` commands to read events, and keeps the last assistant
text as `final`. Keep live traces and credentials outside Git.

Exit 0 means the trace satisfies the spec. Exit 1 means a required event is missing
or a forbidden action occurred. Exit 2 means the JSON is malformed.

## Limits

The checked-in traces are synthetic fixtures. A passing fixture proves the grader and
spec work, not that a live agent followed the skill. Tier 3 does not execute trace
content, call a model or prove delivery. Collect live traces from the host session,
redact secrets and store them outside Git; grade them with the same command.
