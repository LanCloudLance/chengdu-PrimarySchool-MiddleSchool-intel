<!-- OPENPRD:GENERATED
adapter=codex
source=command:fleet
version=0.1.11
checksum=595a75af52beb7b4
-->

# OpenPrd Fleet

Audit or update historical projects. Start with `openprd fleet <root> --dry-run`; use `--sync-registry` to backfill the global workspace registry, `--backfill-work-units` for historical PRD identity binding, `--update-openprd` only for projects that already have `.openprd/`, and reserve `--setup-missing` for explicitly selected projects.

Always rebuild state from `.openprd/` before acting.
