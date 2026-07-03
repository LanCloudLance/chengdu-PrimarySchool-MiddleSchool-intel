<!-- OPENPRD:GENERATED
adapter=codex
source=command:run
version=0.1.11
checksum=47d6b75600c42072
-->

# OpenPrd Run

Use the hook-stable OpenPrd execution loop. Start with `openprd run . --context`, inspect the recommended `executionMode` / `parallelPlan`, execute the recommended task/discovery/workflow action, keep per-task verification task-scoped, and reserve `openprd run . --verify` for phase/final readiness or high-risk actions.
When the user gives a historical session ID, task handle, work unit, or a clear requirement/task description, pass `--message <user-prompt>` so `run --context` resolves that explicit target before considering the global active change. Treat session IDs as tool-neutral; do not require or invent tool-specific ID syntax.

Intent gate: `openprd run . --context` is advisory. Execute mutating recommendations only when the current user message explicitly asks for development, implementation, task continuation, deep research/benchmarking, replication, or commit. Stay read-only for planning, analysis, review, explanation, and file-impact questions.

Always rebuild state from `.openprd/` before acting.
