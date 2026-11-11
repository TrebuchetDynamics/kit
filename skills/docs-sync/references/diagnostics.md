# Triage of `autowork tasks prepare` diagnostics

Each diagnostic carries a `class`. Read the summary first:

```sh
autowork tasks prepare --check --summary .          # counts by code and by file
autowork tasks prepare --check --code BROKEN_SOURCE --limit 20 .
```

The first line on standard error states the store that was read: `read: HEAD` or
`read: worktree`. With uncommitted task files, `--check` reads the working tree.

| Class | Codes | Action |
| --- | --- | --- |
| Actionable | `BROKEN_SOURCE`, `TOUCHES_TASK_STORE`, `UNKNOWN_DEPENDENCY`, `SUPERSEDED_DEPENDENCY`, `DRAFT`, `DUPLICATE_TASK`, `OPEN_TASK_UNDER_MET_GOAL`, `LIVE_NOT_AUTHORIZED` | Repair from accepted evidence with the `fix` command. Never invent a field, grant or closure. |
| Actionable | `LEGACY_CONSUMER`, `LEGACY_DOCUMENTATION` in a current file | Repair the file within scope. Task-field edits do not fix it. |
| Advisory | `GOAL_WITHOUT_WORK`, `IN_FLIGHT`, `NOT_RUNNABLE` | Report it. Add work only from evidence. Leave an `IN_FLIGHT` contract alone; its detail names the slot state, attempt, process and age. |
| Intentional | A legacy name in `testdata/` or `fixtures/`, or in a path that `.autowork-legacy-allow` lists with a reason | No action. The literal name is the test data. |
| Frozen | A legacy name in a frozen archive or a `doc-ref-guard: record` document | No action. Never edit history to silence it. |

Intentional and frozen hits are counted under `suppressed` and are not listed;
`--all` lists them. A `BROKEN_SOURCE` detail names the nearest existing headings
after `did you mean`.

## Allow an intentional literal

Add one line for each path to `.autowork-legacy-allow` at the repository root:

```text
tools/lint-repo/rules_test.go  rule R1 must reject a root TODO.md
```

The text after the glob is the reason. An entry without a reason allows nothing and
appears under `suppressed.allowlist_problems`.

## Exit status

| Status | Meaning |
| --- | --- |
| 0 | Prepared. Diagnostics, advisories included, are not failures. |
| 1 | Refused or invalid store. |
| 3 | `MIGRATION_DEFERRED`: the runner converts after its drain. |
| 4 | Only with `--fail-on-diagnostics`: actionable diagnostics remain. |
| 120 | An older release only. Python reported it when standard output closed early, for example under `\| head`; it never meant advisories. Current releases keep the status above. |
