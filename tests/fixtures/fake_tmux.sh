#!/usr/bin/env bash
set -e
printf '%s\n' "$*" >> "$FAKE_TMUX_LOG"
case "$1" in
  list-sessions)
    for name in ${FAKE_RUNNING:-}; do printf '%s\n' "$name"; done
    ;;
  has-session)
    target=""
    while [[ $# -gt 0 ]]; do
      if [[ "$1" == "-t" ]]; then shift; target=$1; fi
      shift
    done
    target=${target#=}
    [[ ",${FAKE_RUNNING:-}," == *",$target,"* ]]
    ;;
  kill-session|new-session|switch-client|attach-session) exit 0 ;;
  display-message)
    if [[ "$*" == *pane_current_path* ]]; then
      printf '%s\n' "${FAKE_PANE_PATH:-}"
    else
      printf '%s\n' "${FAKE_PANE_COMMAND:-}"
    fi
    ;;
  *) exit 1 ;;
esac
