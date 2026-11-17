#!/bin/sh
# Copy stdin locally; tmux also keeps its buffer and emits OSC 52 when supported.

session_value() {
    [ -n "${TMUX:-}" ] || return 0
    value=$(tmux show-environment "$1" 2>/dev/null) || return 0
    case "$value" in
        "$1="*) printf '%s' "${value#*=}" ;;
    esac
}

# Copy jobs may inherit the server environment, not the attached desktop's.
# Never evaluate show-environment output as shell code.
if [ "${WAYLAND_DISPLAY+x}" != x ]; then
    WAYLAND_DISPLAY=$(session_value WAYLAND_DISPLAY)
    export WAYLAND_DISPLAY
fi
if [ "${DISPLAY+x}" != x ]; then
    DISPLAY=$(session_value DISPLAY)
    export DISPLAY
fi

if [ -n "$WAYLAND_DISPLAY" ] && command -v wl-copy >/dev/null 2>&1; then
    exec wl-copy
fi
if [ -n "$DISPLAY" ]; then
    if command -v xsel >/dev/null 2>&1; then
        exec xsel -ib
    fi
    if command -v xclip >/dev/null 2>&1; then
        exec xclip -selection clipboard
    fi
fi
if command -v pbcopy >/dev/null 2>&1; then
    exec pbcopy
fi

# Pure SSH: drain input without errors and leave clipboard delivery to OSC 52.
cat >/dev/null
exit 0
