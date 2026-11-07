# Memory and retained data

Sources: [setup preflight](../setup_preflight.py),
[runtime policy](../runtime_defaults.py) and [bundle defaults](../plugins/defaults.json).

Kit does not install or select an external memory provider. Full setup and
bundle-only setup preserve existing provider selection, store bindings and records.
They do not migrate data, start a memory server or change capture policy.
Configuration shape checks still apply before setup writes.

Hermes built-in `MEMORY.md` and `USER.md` files remain separate from external
stores. A shared plugin installation does not prove that profiles share a store.
Inspect the actual provider and profile configuration before relying on recall.
A running service or passing setup check does not prove memory capture or replay.

## Inspection and removal

Use the installed provider's documentation and read-only status commands to inspect
its existing stores and retention policy. Retained text can enter future model
requests. Keep credentials and confidential material out of records that an agent
may send to its configured model provider.

Removing Kit does not uninstall external providers or delete their stores.
Changing a provider does not migrate records automatically. Local deletion cannot
erase earlier model requests, exports or backups. Choose migration or deletion
separately for the exact provider and store. See [removal and recovery](uninstall.md).
