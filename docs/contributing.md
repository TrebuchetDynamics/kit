# Adding and updating skills

Source: [command discovery](../__init__.py) and [native provisioning](../scripts/install_skills.py).

## Work on a repository task

Read README.md, AGENTS.md and the current GitHub issue, native dependencies and
linked PRs. GitHub owns executable scope, acceptance, checks and progress; existing
local task records are preserved migration evidence, not a second queue.

Select work within accepted scope, establish actual workspace/process ownership
and preserve unrelated changes. Use an isolated worktree when concurrent writing
needs it. `/work` supports explicit manual implementation; `/autowork` only
redirects to GitHub/Orbi. Orbi remains paused pending live qualification.

Make a scoped change, run affected acceptance checks and independent review, and
commit only attributable verified work. Use the issue/PR's actual evidence for
closure; a local commit is neither publication nor live acceptance. Honor caller
limits and human-only gates. No removed executor or task CLI is required.

## Add or update a skill

```text
skills/
  my-skill/
    SKILL.md
    references/   # optional
    scripts/      # optional
```

Every public skill entry must directly link to the
[shared Ponytail method](../skills/shared/PONYTAIL.md) and the
[shared writing rules](../skills/shared/COMMUNICATION.md). Apply both within the
skill's scope. Keep vendored protocols byte-exact behind local adapters, as in
[Impeccable](../skills/impeccable/SKILL.md); do not rewrite upstream pins to add policy.
`tests/test_ponytail_bundle.py` checks coverage, provenance and native provisioning.

Use a folder name of 1–32 lowercase letters, digits, hyphens, or underscores,
starting with a letter or digit. The folder determines the command name; keep
the skill's frontmatter `name` consistent with it (enforced only for portable
adapters). Most folders are registered automatically; `scripts/workflow_commands.py`
registers both spellings for Plan With Me, Plan For Me and Docs Sync, and
`scripts/autoresearch_commands.py` registers the research selectors. Underscores become hyphens
in CLI commands and Telegram uses underscores: `my_skill` becomes `/my-skill`
in CLI chat and `/my_skill` in Telegram. `my-skill` and `my_skill` cannot coexist.

Every immediate child containing `SKILL.md` is discovered at plugin startup, except
the retired `repo-docs` and `repo-interview`; `grill-me` gets a command but no
separate skill identity while `plan-with-me` exists. Folders without `SKILL.md` are
ignored. Invalid names, ambiguous aliases inside the bundle, or skill paths pointing
outside it cause an explicit plugin-load error. A clash with an existing Hermes or
plugin command only logs a warning and skips that command.

For a GitHub installation, publish your skill changes and run:

```sh
hermes plugins update kit
hermes gateway restart
```

For a local symlink installation, edit this checkout and restart instead. New commands are
discovered on startup, not watched live. A restart does not refresh a skill already
copied into the profile's native skill directory; use `/autowork update` for that.
Telegram's menu has limited capacity; the bundle prioritizes only the five workflow
commands in [`scripts/telegram_menu_policy.py`](../scripts/telegram_menu_policy.py).


### Skill style

Write a skill the way the pinned
[Writing For Agents](../skills/writing-for-agents/SKILL.md) reference teaches it
(mattpocock's `writing-for-agents`, formerly `writing-great-skills`). Load
`/writing-for-agents` for a real editing pass. The [skill standard](skill-standard.md)
is the review checklist and records where Autowork differs from that reference; these
are the parts that decide review.

- **Pointer wording is the trigger.** The description and any always-loaded line name
  what the material is and the distinct branches that should reach it. One trigger per
  branch; drop synonyms that rename the same case.
- **Steps first, reference behind a pointer.** A reader of the skill follows an ordered
  sequence. Move material only some branches need into `references/` and keep a live
  link. Inline what every branch needs.
- **One meaning, one home.** State a rule once, in the file that owns it, and point at
  it from elsewhere. Do not cache what the environment shows (`package.json`, `--help`
  output, the directory layout).
- **State the positive target** and a completion criterion the agent can check. Keep a
  prohibition only as a guardrail that cannot be phrased positively.
- **Hunt no-ops.** A sentence the model already obeys costs tokens to say nothing.
  Delete the sentence, not just its words.
- **Prefer a leading word.** One pretrained token (_no-op_, _sprawl_, _pointer_) beats a
  spelled-out triad, and anchors the behaviour the same way every run.
- **Cut sprawl by disclosure, never by losing a contract.** Length alone is a smell, not
  a defect; a flat rule set on one topic can stay in-file. Keep every phrase a test,
  host or user relies on, and move text rather than restating it.

A documentation edit is not new authority. Read the skill, its adapter, its references
and the tests that read them before editing, and report lines removed with the checks
you ran.

## Portable hosts

Claude Code, Codex and Pi load [portable adapters](../adapters/skills/COMMON.md), not
the Hermes entry point. Add or update the corresponding adapter and its local
references; every adapter keeps `disable-model-invocation: true` and an explicit-only
`agents/openai.yaml`. Pi commands are declared in [adapters/pi.mjs](../adapters/pi.mjs);
the Claude Code marketplace entry in `.claude-plugin/marketplace.json` lists the
adapters folder. Validate both
package metadata and command dispatch using [the cross-host checks](cross-host.md#behavior-and-verification).
Installing or updating Hermes does not install the Codex or Pi package.
