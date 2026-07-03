# Codex-Cursor Agent Loop

This folder is a file-based mailbox between Codex and Cursor.

## Roles

- Codex reviews, validates, sets acceptance criteria, and writes the next Cursor task.
- Cursor executes the task, changes files, runs commands, and writes the result back.

## Files

- `cursor_task.md`: Codex writes the next executable task for Cursor.
- `cursor_result.md`: Cursor writes execution results for Codex.
- `loop_state.md`: shared status and stopping criteria.

## Cursor Protocol

1. Read `cursor_task.md`.
2. Execute only the requested task.
3. Run the requested verification commands.
4. Write `cursor_result.md` using the template in that file.
5. Stop and wait for Codex review.

## Codex Protocol

1. Read `cursor_result.md` and latest project diff.
2. Run review/verification commands when possible.
3. Decide PASS / FAIL / conditional PASS.
4. If more work is needed, overwrite `cursor_task.md` with the next task.
5. If all stopping criteria are met, write final PASS in `loop_state.md`.
