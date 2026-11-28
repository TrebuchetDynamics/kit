# First use in a project

Install Kit into your coding-agent host first ([installation](installation.md),
[cross-host setup](cross-host.md)). Then start that host in the intended project.
The examples use Pi spelling; Claude Code prefixes `/kit:` and Codex `$kit:`
(for example `/kit:plan-with-me` or `$kit:plan-with-me`).

## CLI smoke check

Leave the Kit source checkout and start the host in the intended repository:

```sh
cd /path/to/your-project
pi-bolt        # or: claude, codex
```

In that chat:

```text
/plan-with-me questions only: help me clarify a caching improvement; ask one question, then stop
```

Success means a relevant question arrives without file changes. Check the project's
Git status/diff against its pre-test state. This checks conversational invocation,
not documentation generation or autonomous implementation. Missing provider/tool
errors are failures to resolve, not reasons to report a successful workflow.

## Core-only requirements interview

After the smoke check, use the bundled interview to clarify a real requirement
and produce a decision summary in chat:

```text
/plan-with-me questions only: help me define a tiny CLI that counts nonempty lines in a text file. Ask one question at a time about inputs, blank lines and errors. When I say finish, summarize my answers, open questions and one concrete acceptance example in chat. Do not save files or create tasks.
```

Answer the questions, then say `finish`. Expected evidence is a useful summary
grounded in your actual answers, with unresolved choices left open and no file
changes. This uses the configured model and ordinary repository read access;
Questions-only mode does
not run docs-sync Maintain and needs no Graphify, memory or speech service.
This is an operator-run exercise, not a recorded clean-install/model test.

## Optional: see decisions become a task

This exercise writes documentation and a GitHub issue; it needs a configured model,
file/terminal tools and authenticated GitHub issue-write access. Saving answers uses narrow docs-sync Maintain. A small utility
with clear requirements can use direct source evidence without Graphify. Broader
architecture or dependency analysis may benefit from that integration; Kit does
not install it. No implementation worker is started here.

Use a disposable GitHub-backed repository with no real product data, no active
delivery deployment and a configured model. Command registration alone is not
readiness for this exercise. In the host's chat, try:

```text
/plan-with-me Plan a tiny CLI that counts nonempty lines in a text file. Ask me the missing requirements, then save my accepted answers and one bounded GitHub issue under ai-planning. No dispatch; do not implement, commit or push.
```

Answer the interview. Expected evidence: the existing/new design owner records
your actual accepted decisions; GitHub contains the complete bounded issue with
acceptance, checks and verified native dependencies. Inspect issue bodies and
readiness directly. For a no-dispatch exercise, request `ai-planning` explicitly;
publication may otherwise be consumed by an existing deployment. The final response
names changed paths, issue URLs and observed readiness, not presumed execution.
Retained fix/apply modes keep their own scope and PR/review gates. This exercise does not
activate Orbi or qualify live delivery.

These are operator-run live checks, not recorded model test results.

## Update or remove

Refresh every installed host with `./install.sh update` from a Kit checkout, or
`/update-kit` from a host. Then start a new host session so it discovers the
updated skills, and repeat the smoke check. See
[cross-host updates](cross-host.md) for each host's own update command and
[removal and recovery](uninstall.md) for removing the packages.
