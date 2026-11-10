#!/usr/bin/env bash
# Compatibility dispatch: the canonical launcher moved under the Autowork component.
set -uo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec "$here/../pi-autowork/bin/pi-autowork.sh" "$@"
