#!/usr/bin/env bash
# pi-autowork.sh: run Autowork's Parallel Autowork engine with Pi workers.
#
# The engine (pi-autowork/engine/owner_cycle.py --parallel) plans, dispatches,
# verifies and closes tasks; the pi-autowork component (pi-autowork/pi_autowork/)
# drives its coordinator loop and supplies what the engine leaves to the host: Pi
# workers with model choice and fallback, an independent verification step,
# a session branch merged into the main branch at the end, locking, graceful shutdown
# and a systemd service. This file only finds that component and runs it; the
# component then continues in the toolset release it resolves. See --help.
set -uo pipefail
# A reload (SIGHUP) that arrives before the runner installs its handler, while it starts or
# re-executes, must not end it: systemd counts death by SIGHUP as a clean exit and does not
# restart the unit. Ignored here, and so through exec, until the runner's handler replaces it.
trap '' HUP
# A deliberate `autowork stop` is terminal for authority: an automatic `Restart=on-failure`
# must not resolve and run any release after it. `autowork start`/`restart` clears the marker
# beside the unit's settings file before starting again. Workers and verifiers already
# launched by a stopping runner keep their own path.
helper=
for arg in "$@"; do
  case $arg in --worker|--verify|--verify-batch) helper=1 ;; esac
done
if [[ -z $helper && -n ${PI_AUTOWORK_ENV_FILE:-} && -e ${PI_AUTOWORK_ENV_FILE}.stopped ]]; then
  printf 'pi-autowork: deliberately stopped; not reviving the previous release or push grant. Run autowork start to re-verify and start.\n' >&2
  exit 0
fi
LAUNCHER=$(readlink -f "${BASH_SOURCE[0]}")
SCRIPT=${PI_AUTOWORK_SCRIPT:-$LAUNCHER}
is_component() { [[ -f $1/pi_autowork/cli.py ]]; }
# Workers inherit the runner's component; otherwise PI_AUTOWORK_TOOLSET, this file's
# own release, then the package Pi loads (a copy of this file in a repository).
COMPONENT=${PI_AUTOWORK_COMPONENT:-}
if ! { [[ -n $COMPONENT ]] && is_component "$COMPONENT"; }; then
  COMPONENT=''
  for candidate in "${PI_AUTOWORK_TOOLSET:+$PI_AUTOWORK_TOOLSET/pi-autowork}" "$(dirname "$LAUNCHER")/../pi-autowork"; do
    [[ -n $candidate ]] && is_component "$candidate" && { COMPONENT=$candidate; break; }
  done
  if [[ -z $COMPONENT ]]; then
    source=''
    while IFS= read -r line; do
      line=${line#"${line%%[![:space:]]*}"}
      if [[ $line == /* ]]; then
        if is_component "$line/pi-autowork"; then
          [[ -z $COMPONENT ]] && COMPONENT=$line/pi-autowork
          if [[ ${source%% *} == git:github.com/TrebuchetDynamics/kit ]]; then
            COMPONENT=$line/pi-autowork
            break
          fi
        fi
      else
        source=$line
      fi
    done < <("${PI_BIN:-pi}" list 2>/dev/null)
  fi
fi
if [[ -z $COMPONENT ]]; then
  printf 'pi-autowork: Autowork not found. Install it in Pi (pi install git:github.com/TrebuchetDynamics/kit) or set PI_AUTOWORK_TOOLSET.\n' >&2
  exit 2
fi
command -v python3 >/dev/null 2>&1 || { printf 'pi-autowork: Missing required command: python3\n' >&2; exit 2; }
# Bootstrap is stdlib-only: pin the entire component before cli.py can import
# coordinator/worker modules from a package being updated in place.
exec python3 "$COMPONENT/pi_autowork/release.py" launch "$COMPONENT" "$SCRIPT" "$@"
