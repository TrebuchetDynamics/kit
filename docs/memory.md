# Memory and retained data

Source: [suite installer](../scripts/install_menu.py).

Kit does not install or select an external memory provider. Installation
preserves existing provider selection, store bindings and records.
It does not migrate data, start a memory server or change capture policy.

A shared plugin installation does not prove that sessions share a store.
Inspect the actual provider configuration before relying on recall.
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
