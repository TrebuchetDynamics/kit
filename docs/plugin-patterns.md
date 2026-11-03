# Patterns learned from similar Paseo plugins

## Sources inspected

This comparison inspected public documentation and selected source files, not installed or executed third-party plugins.

- [Task Viewer](https://github.com/akoharu/paseo-task-viewer): multi-source task search, grouped work and visible filter counts. Its [task screen at d6c28bac](https://github.com/akoharu/paseo-task-viewer/blob/d6c28bac5fc799418bb42874efcd4d64d9de65bf/client/tasks-screen.tsx) distinguishes unmatched filters from loading and computes counts after search/filtering.
- [Dey11's Linear plugin](https://github.com/Dey11/paseo-plugins/): paged issue search with explicit confirmation for mutations. Its [panel at ca3bd5ea](https://github.com/Dey11/paseo-plugins/blob/ca3bd5ea3e157dde6fe66e5d3db5aab47413553c/plugins/linear/main.client.tsx) displays one result page with Previous/Next controls and resets pagination after search changes.
- [Linear Todo](https://github.com/trackid-com/paseo-linear-plugin): its README describes editable handoff previews, foreground-only refresh, server-side credential handling and a shared read cache.
- [Paseo quickstart](https://paseo.sh/docs/plugins.md) and [reference](https://paseo.sh/docs/plugins/reference.md): current runtime boundaries, native surfaces, selected-host ownership and theme requirements. Similar plugins target different SDK generations; their imports are not automatically compatible with our pinned 0.14 SDK.

## Applied: bounded task browsing

Autowork already supports task, goal, runtime and section filters. The missing feedback was whether the queue was empty or the filters simply matched nothing, and the task screen rendered the entire filtered queue inside a ScrollView.

The task and blocker views now:

- Display the displayed range, filtered count and complete snapshot count.
- Provide a single Clear task filters action.
- Distinguish no tasks, no blocked tasks, unmatched filters and read failures.
- Render at most 25 task summary rows per page, with accessible Previous/Next controls.
- Filter and group before paging, repeat the goal heading at each page boundary, reset to the first page on filter changes and clamp the page when polling shrinks the queue.

This is local presentation pagination over the existing authoritative task snapshot, not a new upstream cursor API. Changing pages or filters does not send another task RPC. It bounds rendered task summaries, not snapshot transfer size, owner-question rows or total screen complexity. Physical-device memory, responsiveness and battery measurements remain pending.

The implementation adapts the interaction patterns without copying third-party implementation code or adding dependencies.

## Keep existing safeguards

Foreground gating, bounded backoff, shared server-side read collection, explicit confirmations and server-only execution policy already exist here. Retain them rather than replacing them with simpler example code.

Do not copy automatic agent handoff or status updates: Autowork owns execution, accepted scope and completion evidence. A task list must not create another scheduler, accept a proposal or close a task as a side effect of navigation.

Do not adopt legacy browser globals, root-level mixed runtime modules, unscoped caches or permissive version ranges from older examples. Our current native and selected-host boundaries remain authoritative.

## Candidates for later work

A read-only task attachment source could help discuss an exact committed contract in an agent conversation, following Paseo's official attachment pattern. It requires a separate bounded snapshot contract, explicit data-disclosure wording, host/repository/revision binding and tests that attachment selection never grants execution authority. It is not implemented by this change.

Real Android/Desktop checks remain the highest-priority qualification gap. List pagination does not substitute for those checks or justify widening compatibility requirements.
