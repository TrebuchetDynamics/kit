# Watchdog

The 100x skill arms this for unattended runs and fill clocks, and a watchdog message resumes a dead thread with it.

An unattended run has to survive provider hiccups and has to end. The watchdog is a scheduled message posted into this thread every few minutes. While you work it is noise and you ignore it. After a failed or interrupted turn it is the nudge that restarts you.

Done when a watchdog is armed and recorded (or the config says off), and at finish the scheduled task is deleted and the record is cleared.

## Arm it (stage 0, unattended runs and fill clocks)

1. `100x config get watchdog.mode`. `off` means log that and stop here.
2. Does your app have a way to repeat a prompt into this thread, such as a loop, a cron or a scheduled task?
   - No. Log "no watchdog, this app has no scheduler", say so in the pre-flight, and carry on. `.100x/STATE.md` is always true, so a dead thread continues with the `100x-continue` skill. Skip the rest of this section.
   - Yes. Make a task in this session every `watchdog.intervalMinutes` minutes with the text that `100x watchdog prompt` prints, so it posts into this thread and not a new one. Run `100x watchdog record <task id>`.
3. Log it. `100x log ops "armed the watchdog" "an unattended run needs a revive path" "<task id>"`.
4. Tell the pre-flight message that the watchdog is armed and the interval.

A fill clock needs the watchdog even when the owner is awake, because a thread that ends its turn early is the usual way a long run stops. The tick makes it carry on. `100x finish` refuses until the work time is over, so a tick never ends in a finish by accident.

## While you work

Keep `.100x/STATE.md` true at every stage boundary. Three lines drive a continue. `Stage:`, `Next:` and `Open risks:`. `100x status` prints them with asks, decisions and git, and says FINISHED or NOT FINISHED.

## When a tick arrives

- You are mid turn or waiting on a tool. Ignore it. Do not reply.
- You started a judge or a helper and ended the turn to wait for it. Look once. A judge is done when its findings file ends with its `Drifting:` and `Better:` lines, and a night child is done when `100x night status` says it ended. Done: carry on with the result. Still running: end the turn, because its end wakes you. Never start a second judge for the same loop.
- You are idle and the last turn ended on an error. Run `100x status`, log one line saying what failed (`100x log resume "..." "..." "<error or reason>"`), and continue from `Next:`.
- `100x status` says FINISHED. Run the disarm steps below, once.

## Disarm it (stage 8, before the final message)

1. Delete the task with the id in `.100x/watchdog.json`, using your app's own tool. `100x status` shows it too.
2. `100x watchdog clear`.
3. `100x finish` prints a reminder while the record exists, so an unfinished disarm shows up.

## What is proven and what is not

Measured. `100x watchdog prompt`, `record` and `clear` are covered by tests, and the text of the tick names each way a judge or child shows it is done.
Unproven. Whether a scheduled tick reaches a thread whose last run failed, in any app. If ticks never arrive after a failure, a dead thread resumes with the `100x-continue` skill.
