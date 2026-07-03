<!-- OPENPRD:GENERATED
adapter=codex
source=command:grow
version=0.1.11
checksum=94b531278e4bb8a9
-->

# OpenPrd Grow

Treat grow as an end-of-task review layer, not an in-task interruption. Auto-apply whitelisted tool-recognition fixes such as detected code extensions; queue user preferences, project governance rules, and OpenPrd default behavior as candidates, then run `openprd grow . --review` at wrap-up for user confirmation.

Always rebuild state from `.openprd/` before acting.
