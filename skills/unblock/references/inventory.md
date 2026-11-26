# Unblock fleet inventory

From a Kit checkout, run:

```sh
python3 -B skills/unblock/scripts/inventory.py --json
```

From another directory, use the absolute path to the same script. JSON is the default.
Use Python 3.11+ on Linux or macOS and an authenticated GitHub CLI with repository
read access and support for `gh api --paginate --slurp`. The command uses
[Orbi's local status discovery](../../orbi/references/lifecycle.md#host-inventory) for
config and scheduler evidence. Only `source_repos` in discovered local configs
supply repositories; the current Git remote and other hosts do not. The command
never changes labels, issues, PRs, config or scheduling.

## JSON v1

The top-level object contains `schema_version: 1`, `local_coverage` (the local
status report's `state`, `scope`, `managers` and `problems`), and `repositories`.
Repository names in `repo` are lower-case `owner/name`, sorted and deduplicated.
Each repository has the following fields:

| Field | Contents |
| --- | --- |
| `deployments` | Observations sorted by `config` path, `manager` and `unit`. Includes `kind`, `state`, `scheduler`, `timer_state` and `worker_state` from local status. A config with no bound unit has a `config-only` row (`prepared-only`, with null manager and unit). Multiple configs or units can refer to one repository. |
| `open_issues` | Issues with `ai-blocked`, `ai-fix-needed`, `ai-decision`, `ai-in-progress`, `ai-pr-opened`, or `ai-planning` without `ai-epic`. Rows contain `number`, `url`, `title`, sorted `labels`, `failure`, `open_question`, and `live_local_worker`. |
| `closed_issues` | Rows with `number`, `url`, `title` and sorted `labels`. Includes the open state labels plus `ai-ready`, `ai-awaiting-merge`, `ai-merged`, `ai-needs-detail` and `ai-paused`; `ai-planning` on a closed epic also counts. A purpose or gate label alone is not a delivery state. |
| `open_prs` | All open PRs, linked or not. Rows contain `number`, `url`, `head` (branch), `head_sha`, `mergeability` (`MERGEABLE`, `CONFLICTING`, `UNKNOWN`) and `required_checks`. |
| `errors` | Array of repository read gaps, empty if none. An unavailable list is `null`, not `[]`. A detail error can leave a list populated but the affected detail unknown. |

Issues and PRs are sorted numerically. `failure` is null or has the latest
`orbi:failure:v1` `reason_code` and `action_code`. `open_question` is null or has
`id`, `question` (text) and `recommended_option` (the option object from the
marker, or null). The inventory shows the latest `orbi:question:v1` unless a
matching `orbi:answer:v1` record appears in the same or a later comment. These
markers are observations, not a verdict on answer authority or retry safety.
`live_local_worker` is `true` for a verified local issue binding, `false` when no
worker was observed with readable local evidence, or `null` when a worker could
not be attributed or local observation is incomplete. It is not a fleet-wide
ownership guarantee.

`required_checks` contains `result` and `checks`. The latter contains reported
required checks with `name`, `state`, `bucket` and `link`. The result is `fail`
(failed or canceled), `pending`, `pass` (all reported checks passed or were
skipped), `not_reported` (no required check reported), or `unknown` (read failed
or the head could not be confirmed). `not_reported` does not prove no checks are
configured. Even `pass` is not proof that GitHub can merge the PR.

Exit `0` means the inventory reads completed, not that the fleet has no blockers.
Exit `1` still emits JSON and reports gaps on stderr. Restore config or scheduler
read access for `local_coverage` problems; for GitHub read errors, check `gh`
authentication and repository access. Use unaffected observations and re-read
current issue, PR and worker evidence before any recovery write.
