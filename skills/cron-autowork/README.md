# Cron pre-run script

This folder is not a skill. Its `SKILL.md` was removed, and no command, adapter or
docs entry registers it. The folder stays because Hermes runs a cron job's pre-run
script from `HERMES_HOME/scripts`, and the plugin copies
[`pi-autowork/scripts/autowork-start-notice.py`](../../pi-autowork/scripts/autowork-start-notice.py) there for jobs
that already reference its installed filename. The old
[`scripts/autowork-start-notice.py`](scripts/autowork-start-notice.py) source path
is a compatibility dispatcher, not the payload to copy into a profile.

Schedule work with the host's own cron command. The plugin does not add a scheduling
workflow.
