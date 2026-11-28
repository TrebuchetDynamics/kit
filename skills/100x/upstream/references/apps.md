# Agent apps

100x is skill folders plus one command line tool, so it runs in any app that loads `SKILL.md` folders and can run shell commands. Three things differ per app. How a skill is called, where models are listed, and how the judge starts. Model ids are whatever the app or tool accepts, so write the ones its own list shows and never carry ids between apps.

## Calling a skill and where it is installed

| App | Call | Skill folder | Status |
|---|---|---|---|
| Cursor | `/100x` | `~/.agents/skills` or `~/.cursor/skills` | used by the author |
| Claude Code | `/100x` | `~/.claude/skills` | used by the author |
| Claude Code, as the plugin | `/100x-engineer:100x` | the plugin's own folder, which Claude Code keeps | the same skills as a copy, not run by the author yet |
| Codex | `$100x` | `~/.codex/skills` or `~/.agents/skills` | folder from its docs, untested here |
| opencode | name it in words | `~/.config/opencode/skills` | folder from its docs, untested here |

The call is the skill's name, so the modes are called the same way: `/100x-status` in Cursor and Claude Code, `$100x-status` in Codex. In opencode, name the skill in words.

`100x install --also claude,codex,opencode,cursor` links the skills into the extra folders. A skill folder an app does not read is harmless.

## In Cursor every helper starts through the SDK

In Cursor a helper is a judge, an arm of a bake-off or a child, and it starts through the Cursor SDK with `100x helper run`. Never with the Task tool and never with `cursor-agent`. Measured on the owner's account: the Task tool took `muse-wonder-1.0-xhigh` and every helper in the hooks log still ran `composer-2.5-fast`, and `cursor-agent -p --model muse-wonder-1.0-max` stopped with "out of fast requests" because the account runs on an unlimited slow queue. The SDK started a real Muse Wonder helper at max effort and 300k context in about 5 seconds, and its result names the model that ran.
- Once per machine: `100x helper setup` installs `@cursor/sdk` into `~/.100x`, then `100x helper login` opens the Cursor login page and the owner approves it. The SDK keeps the key for 90 days, `CURSOR_API_KEY` works instead, and no command prints a key.
- `100x helper models` lists the ids this account can use with their parameters. Use them exactly. The owner's rule names `muse-wonder-1.0-max`, which in the SDK is `--model muse-wonder-1.0 --effort max --context 300k`.
- **Never MAX mode, always the 300k window.** The catalog marks every 1m window as a MAX mode variant, and the default variant of a model with a window is one of them (`muse-wonder-1.0` defaults to `context 1m, reasoning_effort xhigh`). A helper started without `--context` would therefore run in MAX mode without a word. `100x helper run` refuses any selection that could mean a MAX variant, so `--context 300k` is required, and a receipt or result that reports MAX mode exits 3. `max` is a reasoning effort and is not MAX mode: `muse-wonder-1.0` at `--effort max --context 300k` is a variant the catalog does not mark as MAX. The SDK result names the model, the effort and the window that ran. In the runs checked it did not report MAX mode itself, so the check is the catalog's variant plus the window the result reports. It also refuses a named 1m window whether or not the catalog flags it, and a selection that no listed variant matches. A helper runs with the task tool off, so it cannot start a subagent of its own. `helper.only` in the global config (`muse-wonder-1.0 reasoning_effort=max context=300k`) locks every helper on the machine to one selection, and `helper.ceiling` limits the number of helpers a night or a run asks for at once. It is not a count of live sessions, and it does not count judges, this thread or other chats. A project file can set neither, and a helper command that hard-codes `--context 1m` is refused.
- `100x helper run --model <id> --effort <level> --context <size> --task-file <file> --cwd <folder>` runs one helper to its end in the foreground and prints the model asked for and the model the SDK reports. Exit code 3 means another model ran, and that run does not count as a run of the model that was chosen. In Cursor run it with `block_until_ms` 0 and wait for its finished notice. A judge goes through `100x review-run` instead, see "The judge as a command" below.
- Do not call `100x review-verify` for these helpers. It reads the hooks log of the Task tool, and the SDK result is the record.

## Waiting for a judge or a child

A judge or a child takes 10 to 60 minutes, and what you do meanwhile depends on the app.

- **The app wakes your thread when the helper ends.** When the reply that started the helper says it will, do not sleep and do not poll. Do the work that does not need the result: commit, keep `STATE.md` true, run the next shots, write the next ask. Then end your turn, and the end of the helper starts the next one. Read the result once then. A watchdog tick that arrives meanwhile is answered as `references/watchdog.md` says.
- **The app does not.** Wait inside the turn. Run `sleep 240` in the shell, check the findings file, and repeat. A tool call that waits on the result gives up after about a minute, so never use one.

Either way the log holds the start and the task id, so a resumed thread knows one is running and never starts a second judge for the same loop.

## Where the models come from

- Cursor. `100x helper models`. The effort and the context window are parameters of the model, set with `--effort` and `--context`.
- Claude Code. No list command. `--model` takes an alias such as `opus`, `sonnet` or a full model name, and `--effort` takes `low`, `medium`, `high`, `xhigh` or `max`.
- Any other app. Use its own model menu or list command. With neither, ask the owner for the names.

## The judge as a command

When `review.command` is set, `100x review-run` starts it in the background. It is set only in the global config, because a shell command in a project file would run for anyone who opens that project. The command reads its settings from environment variables. `X100_MODEL`, `X100_EFFORT`, `X100_TASK`, plus `X100_OPT_<ID>` for every other option. Empty ones are left out by the `${VAR:+...}` form below. The judge runs unattended, so nothing can answer an approval prompt. No template starts an app with its approvals off. Each one names the commands the judge may run in an allow rule, and, when the owner's own settings add no broader allow rule, the app refuses everything else. The judge reads the project, writes its findings and screenshots under `.100x/`, runs `100x shots` and `100x text lint`, and starts the project with its own run command. The rule covers only the test, build and lint scripts, so add the project's run command to it, spelled out: `Bash(npm run dev *)` for `npm run dev`. The judge still runs the owner's project code with the owner's permissions on the owner's machine. Use it on projects the owner wrote. For a project the owner cloned or was sent, judge through the app's own subagent tool instead, because that project's files are part of what the judge reads.

Write the command and the model together. `100x config set review.command '<command>' --global` and `100x config role review --model <id> [--option effort=<level>] --global`. A command wins over the app's own subagent tool, so a person who uses two apps clears it in one of them with `100x config unset review.command --global`.

### claude

Flags read from `claude --help`, and run against `claude` 2.1.332 with `--setting-sources project`. It wrote a file under `.100x/` and refused one outside it. It ran 8 commands the rule names (`git status`, `git diff`, `git log`, `npm test`, `npm run build`, `100x text lint`, `100x shots`) and refused 8 it does not (`git push`, `git commit`, `100x doctor`, `100x install`, `100x browsers`, `npm run deploy`, `npm run build-and-ship`, `rm -rf`). A hook in the owner's own settings that rewrites shell commands can make a command miss its rule, and then the judge is refused it. No review has come back yet. The task goes before `--allowedTools`, which takes every word after it as a tool. With `--setting-sources project`, `Edit(path)` rules limit where its file tools write. The rule names the two `100x` tools the judge's task offers, `shots` and `text lint`, and nothing else of `100x`: `install`, `browsers`, `helper` and `upstream` write outside the project or use the network, so they are refused. It allows `npm run` for `build` and `lint` only, because any other project script can deploy. The Bash commands the rule allows are not limited to `.100x/`. `git diff --output=<file>` writes where it is told, and `npm test` and the two scripts run the project's own code with the owner's permissions, which can write anywhere the owner can.

The rules add approvals to the ones in the owner's own settings. They do not take any away. To keep the owner's user-level settings out of the judge, add `--setting-sources project` after the task. That also drops the owner's own hooks and deny rules for the judge, so add it only when the owner wants a judge with nothing but this rule. The project's own `.claude/settings.json` still loads, so the limits hold only when that file adds no allow rule broader than the listed commands.

```sh
claude -p "$X100_TASK" ${X100_MODEL:+--model "$X100_MODEL"} ${X100_EFFORT:+--effort "$X100_EFFORT"} --allowedTools "Read,Glob,Grep,Edit(.100x/**),Bash(100x shots *),Bash(100x text lint *),Bash(git status *),Bash(git diff *),Bash(git log *),Bash(npm test *),Bash(npm run build *),Bash(npm run lint *)"
```

### cursor

The Cursor SDK, through `100x helper run`. Run end to end on the author's account with `muse-wonder-1.0` at max effort and 300k context. The helper wrote a file and answered, and the result named `muse-wonder-1.0` with those parameters. The same prompt on `composer-2.5` answered "Composer" and reported no reasoning tokens, and on Muse it answered "Muse Wonder" with reasoning tokens, so the model that was asked for is the model that ran. Local helpers have full access to the folder given and to the machine, the same trust as any command judge.

```sh
100x helper run ${X100_MODEL:+--model "$X100_MODEL"} ${X100_EFFORT:+--effort "$X100_EFFORT"} ${X100_OPT_CONTEXTWINDOW:+--context "$X100_OPT_CONTEXTWINDOW"} --task "$X100_TASK" --stream
```

Set it with `100x config set review.command '<the line above>' --global` and `100x config role review --model muse-wonder-1.0 --option effort=max --option contextWindow=300k --global`.

The Task tool is not a way to start a helper in Cursor, and neither is `cursor-agent`. Cursor logs a Task helper start only when some hook is set for `subagentStart`, and `100x review-verify` reads that log, so it can check an old Task helper and nothing else.

### codex

From memory of its docs. Check `codex exec --help` first.

```sh
codex exec ${X100_MODEL:+-m "$X100_MODEL"} ${X100_EFFORT:+-c model_reasoning_effort="$X100_EFFORT"} --sandbox workspace-write "$X100_TASK"
```

The sandbox lets it write in the project and keeps it out of the rest of the machine. If the project's run command needs more, widen it from the app's own docs, one rule at a time, and never to full access.

### gemini

From memory of its docs. Check `gemini --help` first.

```sh
gemini ${X100_MODEL:+-m "$X100_MODEL"} -p "$X100_TASK"
```

Run this way it reads and answers, and stops at any tool that needs approval. Add the commands the judge needs to the app's own allow list, which `gemini --help` names, and never a mode that turns approvals off.

### opencode

From memory of its docs. Check `opencode run --help` first. The model is `provider/model`.

```sh
opencode run ${X100_MODEL:+-m "$X100_MODEL"} "$X100_TASK"
```

## Choosing a judge on your own

Nobody has to name a judge for a run to work. Setup proposes one, and a run with none picks the strongest model from a different vendor than the builder that the app or a command on this machine can start. The reason a judge must differ from the builder is that two copies of one model share blind spots. If nothing else can start, the run is UNREVIEWED and says so. Where `helper.only` is set, the judge is the locked selection, started with `100x helper run`, and no other model or vendor is substituted.
