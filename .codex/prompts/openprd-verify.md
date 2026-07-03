<!-- OPENPRD:GENERATED
adapter=codex
source=command:verify
version=0.1.11
checksum=b7c2893a4f1a6b9d
-->

# OpenPrd Verify

Run `openprd run . --verify`. It verifies standards, workspace validation, the currently focused change structure (not just the global active change), and active discovery state, then reports `taskReady` separately from `workspaceReady`. When `taskReady=true` and `workspaceReady=false`, final reporting must preserve that split; if the only attention gate is `feature-coverage`, describe it as task-ledger or evidence debt rather than a failed implementation.

Always rebuild state from `.openprd/` before acting.
