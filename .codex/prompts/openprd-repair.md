<!-- OPENPRD:GENERATED
adapter=codex
source=command:repair
version=0.1.11
checksum=154cc5ac898a903c
-->

# OpenPrd Repair

Use `openprd doctor .` to identify drift or missing generated files. Run `openprd update .` for generated guidance drift, repair standards/docs manually, then re-run verification.
Codex CLI runtime repair is explicit: use `openprd doctor . --tools codex --fix` or `openprd loop . --run --agent codex --repair-agent` only after the user accepts that OpenPrd will run `npm install -g @openai/codex@latest`.

Always rebuild state from `.openprd/` before acting.
