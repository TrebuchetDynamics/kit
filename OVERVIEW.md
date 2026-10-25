# Autowork

A native Paseo workspace for an existing Autowork installation on a Linux workstation. Inspect runners, task contracts, verification provenance and owner questions from one selected host. Use the workspace panel, Command Center or `aw-*` composer commands to open the relevant view without creating a new coding-agent provider.

Paseo 0.13.x and Autowork prepare API 4 are required. By default all operations are read-only. An operator can opt into staged planning, revision-bound owner answers and selected runner controls through a daemon-side policy file. Every mutation needs explicit confirmation and existing Autowork validation; no task, live-operation or publication authority is invented by the UI.

Planning uses Autowork's existing controller in plugin-owned sessions. Proposals remain unaccepted before Review and Apply. Worker/reviewer processes and Paseo-created Pi sessions are never attached or taken over. Disabling the plugin cancels only its own planning turns and retains upstream histories and work.

The implementation has passed native-component fixtures, the official compiler, an isolated real Paseo plugin-runtime load test and read-only inspection of a real Autowork fleet. Physical Android/Desktop UI and real planning/service-control qualification remain pending. Missing runtime or delivery provenance is displayed as unknown. No external telemetry or additional listening service is used.
