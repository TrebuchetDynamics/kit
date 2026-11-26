#!/usr/bin/env bash
# One entry point: install the pinned Orbi fork CLI, tx, Pi-Bolt and the Hermes, Claude Code, Codex and Pi integrations
# with live progress by default; --verbose expands Hermes detail, --menu selects items.
# `install.sh update` runs the same items as an in-place update of what is installed.
# Live progress and terminal colors: scripts/install_menu.py. See: install.sh --help
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec python3 "$script_dir/scripts/install_menu.py" "$@"
