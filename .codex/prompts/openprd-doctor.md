<!-- OPENPRD:GENERATED
adapter=codex
source=command:doctor
version=0.1.11
checksum=6bb754744962a12e
-->

# OpenPrd Doctor

Run `openprd doctor .` and repair missing AGENTS, skills, commands, hooks, standards, validation gates, or Codex CLI runtime health.
For Codex CLI optional dependency failures, first inspect `openprd doctor . --tools codex`; only run `openprd doctor . --tools codex --fix` when the user explicitly wants OpenPrd to execute the global npm repair command.

Always rebuild state from `.openprd/` before acting.
