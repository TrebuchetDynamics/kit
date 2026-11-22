# tmux profile

Portable tmux assets and the `tx` tmux-session launcher.

This is the maintained `tx`. It started as a copy of
[pi-toolset `tmux/`](https://github.com/TrebuchetDynamics/pi-toolset/tree/main/tmux)
at `4a2dbe5`; pi-toolset's `tx` is deprecated in its favor. Installing this one (`./install.sh`, or the package's `tx` command) replaces a
`tx` installed from pi-toolset; every pi-toolset command works the same.

## Delivery services

`tx` is a tmux session launcher only. GitHub Issues and Orbi own delivery;
`tx` does not install or control a replacement. See
[GitHub/Orbi delivery](../docs/github-native.md). Orbi remains paused until qualified.

## Files

- `tmux.conf` — tmux configuration. Install as `~/.tmux.conf`.
- `style.tmux` — local style overrides. Installed as `~/.tmux/style.tmux` only when missing.
- `git-status.sh` — optional status-bar git segment. Prints the branch name in green when clean and red when changed/untracked.
- `short-path.sh` — optional status-bar path segment. Prints only the last two path folders, e.g. `/tmp/git/pi-package-development-goal` -> `git/pi-package-development-goal`.
- `copy.sh` — stdin-to-system-clipboard helper for mouse and keyboard copies.
- `tx` — installable helper for starting, attaching, listing, and killing configured tmux sessions.
- `install.sh` — installer for the config, clipboard/status helpers, and `tx`.

## Install

The repository-root suite installer (`./install.sh --only tx`, run from the root)
keeps existing tmux configuration and helpers. It refreshes changed regular shell
completion files with adjacent `.bak`/`.bak.N` backups, keeps completion symlinks
(including dangling links), and reports each completion as written, replaced or kept.
Replaced commands move to `~/.local/state/kit/backups/`, outside `PATH`, with only
the newest five retained. Existing bin-directory `tx.bak*` files are left alone;
see the [accepted rules and manual cleanup command](../docs/installation.md#full-suite-from-a-checkout).

The separate installer below is unchanged: its timestamp backups can still collect
beside `tx` on `PATH`; it does not use the suite installer's five-backup retention.

From this directory:

```sh
./install.sh
```

If `tx` is already on your `PATH` from an npm install/link, you can also run:

```sh
tx install
```

Defaults:

- tmux config -> `~/.tmux.conf`
- local style -> `~/.tmux/style.tmux` (kept if it already exists)
- helpers -> `~/.tmux/git-status.sh`, `~/.tmux/short-path.sh`, and `~/.tmux/copy.sh`
- `tx` -> `~/.local/bin/tx`

Existing targets are backed up as `*.bak.<timestamp>` by default. Disable backups with:

```sh
TX_INSTALL_BACKUP=0 ./install.sh
```

Override install locations when needed. When `TMUX_HELPER_DIR` is set, the installed tmux config is rewritten to invoke helper scripts from that directory:

```sh
TMUX_CONF_TARGET=/tmp/tmux.conf \
TMUX_HELPER_DIR=/tmp/tmux \
TX_BIN_DIR=/tmp/bin \
./install.sh
```

`./install.sh --print-paths` prints the resolved install targets without writing.
`tx doctor --install` runs the installer and uses those same paths.

Reload tmux:

```sh
tmux source-file ~/.tmux.conf
```

## Runtime flow

- `install.sh` copies the shared assets into user locations: `tmux.conf`, helper scripts, optional local style, and the `tx` launcher.
- `tmux.conf` shows a navy/teal status bar with the session, short current path, git branch/status, window tabs, zoom state, and host. Periodic refresh remains disabled.
- `tx` reads session aliases from its config file, starts or switches to the matching tmux session, and uses the alias as the tmux session name.
- `style.tmux` stores per-machine colors and is sourced by `tmux.conf` from `~/.tmux/style.tmux`.

## Helper-script contract

The shared config calls `short-path.sh` and `git-status.sh` in the status bar and uses `copy.sh` as its `copy-command`. The installer places all three helpers under `~/.tmux` (or `TMUX_HELPER_DIR`) and rewrites `tmux.conf` to that helper path.

Each status helper takes one argument: the current pane path from `#{pane_current_path}`. `git-status.sh` prints the branch in green when clean and red when changed/untracked; outside git repos it prints nothing.

`copy.sh` reads the selection from stdin. It prefers `wl-copy` when `WAYLAND_DISPLAY` is set, then `xsel -ib` or `xclip -selection clipboard` when `DISPLAY` is set, then macOS `pbcopy`. Missing display variables are read from the tmux session environment, without a hard-coded display. With no usable tool it silently discards stdin; tmux still keeps its buffer and uses OSC 52 for SSH clients that support clipboard access.

For very slow SSH/mobile links, periodic helper calls are disabled by default. To simplify the status further in `~/.tmux/local.tmux`:

```tmux
set -g status-left '#[bg=#{@primary_color},fg=#{@primary_text_color},bold] #S '
set -g status-left-length 40
```

## npm/bin install

The repository package declares:

```json
{ "bin": { "tx": "tmux/tx" } }
```

So `tx` is available when this package (Kit) is installed or linked by npm. The tmux config and status helper scripts still require `tx install`, `./install.sh`, or manual copying.

## Screen resizing

The profile does not set tmux resize options. It leaves `window-size` and `aggressive-resize` at tmux built-in defaults. This is intentional: forcing a manual window size can make mobile SSH clients repaint worse.

Inspect attached client sizes with:

```sh
tmux list-clients -F '#{client_name} #{client_session} #{client_width}x#{client_height} #{client_tty}'
```

If resize/redraw feels slow in a phone SSH app such as Termius, first close old SSH tabs and detach stale tmux clients:

```sh
tmux detach-client -a
tmux list-clients -F '#{client_name} #{client_session} #{client_width}x#{client_height} #{client_tty}'
```

The goal is one attached client, or at least no stale phone clients at very different sizes.

Avoid this as a default fix:

```sh
# Usually worse on mobile; use only as a temporary experiment.
tmux set -g window-size manual
```

Return to normal resize behavior with:

```sh
tmux set -g window-size latest
```

## Mobile controls

The prefix remains tmux's standard `Ctrl-b`, which works with Termius's extra-key row. Useful phone-friendly bindings:

- `Ctrl-b r` — force a full redraw after a reconnect or orientation change.
- `Ctrl-b v` — enter copy mode. Press `v` to select, then `y` or Enter to copy and exit.
- Drag to select — release to copy and exit copy mode. No Shift key or extra key press is needed.
- `Ctrl-b Page Up` — enter scrollback; then use `Page Up`/`Page Down` and `q` to exit.
- `Ctrl-b m` — toggle mouse/touch scrolling for the current tmux server.
- `Ctrl-b t` — toggle the status bar when session details are useful.

Mouse mode is on by default for scrolling, pane selection and drag-to-copy. Drag release, `y` and Enter copy to the tmux buffer and system clipboard through the helper; OSC 52 remains available when the SSH client permits clipboard access. A program that captures the mouse itself still receives the drag. Use `Ctrl-b m` to turn mouse mode off for native terminal selection. The SSH app can have its own copy-on-select setting, which tmux cannot control. `Ctrl-b ]` pastes the tmux buffer even without client clipboard support. Window tabs show each window's number and name, with teal for the current window. Path and git details are limited to leave space for tabs at narrow widths. Synchronized output (`terminal-features` sync) is **disabled by default** because mishandled end-of-frame markers can drop whole frames on some mobile SSH clients; re-enable it by uncommenting the two `terminal-features` lines in `tmux.conf`. Detach and reconnect once after installing so tmux recalculates client terminal features.

## Adopt drag-to-copy in an existing installation

The suite installer (`../install.sh --only tx` from this directory) keeps existing
`~/.tmux.conf` and helpers, so an existing config does not change automatically.
Run it to install the missing `~/.tmux/copy.sh`, then add these settings to
`~/.tmux/local.tmux` (use your helper path if different):

```tmux
set -g mouse on
set -s set-clipboard external
set -s copy-command "~/.tmux/copy.sh"
bind -T copy-mode MouseDragEnd1Pane send -X copy-pipe-and-cancel
bind -T copy-mode-vi MouseDragEnd1Pane send -X copy-pipe-and-cancel
bind -T copy-mode-vi y send -X copy-pipe-and-cancel
bind -T copy-mode-vi Enter send -X copy-pipe-and-cancel
```

Reload with `tmux source-file ~/.tmux.conf`. Alternatively, `./install.sh` in this
directory reinstalls the shared config and helpers with the backups described above.

If the system clipboard does not change, install `wl-clipboard` on Wayland or
`xsel`/`xclip` on X11 and make the desktop display variables available to the tmux
session (reconnect from a desktop terminal). Tool errors, such as an inaccessible
display, remain tool errors; repair that desktop connection. With no usable tool
there is no error; use an OSC 52-capable SSH client or paste the retained tmux buffer
with `Ctrl-b ]`.

## Local/mobile overrides

The shared config sources `~/.tmux/local.tmux` at the end when it exists. Use this file for machine-specific settings only after stale-client cleanup is not enough.

The defaults keep history large, avoid idle status refreshes, and allow slightly slower mobile key sequences:

```tmux
set -g status on
set -g status-interval 0
set -g bell-action none
set -g history-limit 5000
set -sg escape-time 100
set -g repeat-time 750
```

Test one extra setting at a time so rollback is easy:

```tmux
# Optional if your local terminal needs truecolor more than low-byte output.
# set -as terminal-overrides ',xterm-256color:RGB'

# Optional if you prefer phone drag/scroll through tmux instead of the SSH app.
# set -g mouse on
```

Rollback to shared defaults:

```sh
rm -f ~/.tmux/local.tmux
tmux set -g window-size latest
tmux source-file ~/.tmux.conf
```

Keep resize overrides out of shared config unless there is a measured, cross-client reason. The shared profile intentionally leaves tmux resize behavior at defaults.

## User-facing colors

Per-machine colors live in `~/.tmux/style.tmux`, sourced by `~/.tmux.conf`:

```tmux
set -g @primary_color '#06d6a0'
set -g @primary_text_color '#101820'
```

The installer creates this file only when missing, so each PC can keep local colors while updating the shared tmux config. These colors affect the tmux session name and hostname. The current git branch is shown by `~/.tmux/git-status.sh`: green when clean, red when changed or untracked.

## tx config

`tx` reads sessions from:

```text
$TX_CONFIG
$XDG_CONFIG_HOME/tx/session.config
~/.config/tx/session.config

If the legacy `sessions.conf` already exists and `session.config` does not, `tx` keeps using the legacy file.
```

Create a starter config:

```sh
tx init
```

Add the current directory with an explicit alias:

```sh
tx add ga
tx add . ga
```

Add an explicit directory with an explicit alias. Alias-first and directory-first forms are both accepted:

```sh
tx add ga ~/git/agent
tx add ~/git/agent ga
```

Prompt for an alias while adding the current directory or another directory:

```sh
tx add .
tx add ~/git/agent
```

If the target directory already has a config row, the new alias is appended to that row's comma-separated alias list. Each alias must be unique, both within an addition and across the config.

Aliases must be unique. `tx edit` accepts exactly one new alias, not a comma-separated
list. Config updates validate the complete replacement before publishing it. If
validation fails, the original config file remains unchanged.

Inspect, rename, remove, and use:

```sh
tx config
tx ls
tx doctor
tx which ga
tx edit asul azul
tx remove oldalias
tx remove hw1 hw2 hw3 hw4
tx remove 'hw*'
tx ga
```

`tx edit` renames exactly one alias to one new alias, including when prompted. Comma-separated replacement names and names already in use are rejected.

`tx remove <alias-or-pattern> [alias-or-pattern ...]` accepts one or more nonempty
selectors. A literal selects one alias: exact names win, otherwise the shortest
prefix match wins (alphabetical tie-breaker). A selector containing `*`, `?` or
bracket classes matches complete configured alias names case-sensitively and
selects every match, not paths or session names. For example:

```sh
tx remove hw1 'hw[2-4]' 'hw?'  # mixed/overlapping selectors are deduplicated
tx remove '*'                # remove every alias row; keep comments and variables
```

All selectors resolve against the original config before any change. Unknown
literals, no-match patterns (including unmatched brackets), and empty selectors
fail the entire request without changing the config or printing success receipts.
Correct the rejected selector and retry. A successful batch replaces the config
once and prints one `removed: alias=target` line per distinct alias in config
row/key order. Unselected aliases sharing a row are retained. Removal only edits
config entries: it never kills/starts sessions or deletes directories/files, and
aliases whose target directories are missing can still be removed.

Quote patterns in **Bash, Zsh and Fish**: prefer `tx remove 'hw*'`, or escape the
wildcard as `tx remove hw\*`. In default Bash, unquoted `hw*` passes through when
no filename matches; matching files or shell options can change that behavior.
Zsh normally rejects an unmatched unquoted glob before running `tx`; Fish can
also reject unmatched globs. Other unquoted patterns may expand to filenames.
`tx` treats the actual arguments it receives as selectors: it cannot recover the
original token or distinguish expanded filenames from intentional alias names.
When an unknown literal selector names an existing file, directory or dangling
symlink in the current directory, `tx remove` adds a shell-expansion hint with a
quoted example after the error. The example is illustrative, not the recovered
pattern; retry with your intended pattern quoted. No hint is added if no such
path exists, and aliases that resolve successfully are removed normally.
No shell-option changes or completion installation are needed to use selectors.

Alias mutations validate the complete staged config before replacing the original file. Rejected updates leave the original config unchanged and remove the staging file. Valid updates preserve comments, variables, row order, spacing, and existing CRLF line endings.

The installer writes shell completion files for Bash, Fish, and Zsh. It also appends a small Bash source line to `~/.bashrc` when that file exists, so new Bash shells complete aliases automatically. For the current shell, run:

```sh
source ~/.local/share/bash-completion/completions/tx
```

Type `tx samp` and press Tab to complete configured aliases such as `sample`.
If several aliases share the prefix, Tab extends the common prefix; press Tab
again to list matches. Alias arguments also complete after `kill`, `remove`,
`edit`, and `which`, including second and later operands of `remove`. Completion
reads the config each time, including aliases
whose sessions are stopped or whose directories do not yet exist.

Manual completion output is also available:

```sh
tx completion bash
tx completion zsh
tx completion fish
```

Config format:

```text
WORK=~/git
ga,gormes=$WORK/agent
```

Alias prefixes are accepted. Exact aliases win; otherwise the shortest matching alias wins, with alphabetical order used as a tie-breaker.

`tx ls` groups aliases by target directory to save vertical space. Running aliases are green; stopped or missing aliases are red. No status words are printed in the alias list. Colors are enabled by default for SSH terminals; use `TX_COLOR=auto` for TTY-only color, `TX_COLOR=never` to disable, or `NO_COLOR=1` to disable.
