# Codex Mini Loop Status - 2026-06-23

## Loop Result

Status: PASS with one environment note.

PowerShell note:

- The current Codex shell still cannot locate a runnable `pwsh` or `powershell` binary.
- Searched `PATH`, common Homebrew locations, `/Applications/PowerShell.app`, `/usr/local/microsoft`, `/opt/microsoft`, and app extension folders.
- Found only editor PowerShell extension folders, not the PowerShell executable.
- Verification was executed with equivalent local commands from zsh.

## Current Runtime State

- Branch: `feat/chengdu-edu-intel-mvp`
- Worktree: dirty, checkpoint not committed yet.
- PostgreSQL Docker service: running.
- API service: running at `http://127.0.0.1:8000`.
- Review write mode: default read-only, no write token flow enabled.

## Verification Completed

```bash
.venv/bin/python scripts/verify_district_parity.py --year 2026
# ALL DISTRICTS PARITY PASS

.venv/bin/pytest packages/storage/tests packages/api/tests -q
# 34 passed

.venv/bin/python scripts/verify_district_parity.py --year 2025 --db
# ALL DISTRICTS PARITY PASS

.venv/bin/python scripts/verify_district_parity.py --year 2026 --db
# ALL DISTRICTS PARITY PASS
```

## 2026 DB Status Summary

- 锦江: PASS, 24 verified, 3 pending_official.
- 青羊: PASS, 31 verified, 4 pending_official.
- 武侯: PASS, 9 reference, 29 pending_review, 23 pending_official.
- 成华: PASS, 36 verified, 2 pending_official.
- 金牛: PASS, 46 pending_review, 17 pending_official.
- 高新: PASS, 5 reference, 30 pending_review, 6 pending_official.
- 天府: PASS, 38 pending_official.

Interpretation:

- MVP parity is good.
- 2026 is not fully verified data.
- OCR/reference/pending rows must stay visibly labeled in the product.

## Browser QA

Checked through the in-app browser:

- Home page loads.
- Default mapping year is 2026.
- School dropdown has 7 district groups.
- Scope dropdown has 105 options.
- Search for `四川天府新区元音小学` returns one result.
- Result link preserves `?year=2026`.
- Detail page shows 2026 framework, mapping block, and `待官方` badge.
- Back link preserves `/?year=2026`.
- Review page `/review/mappings?year=2026&district=jinniu&status=pending_review` shows `2026 年 · 共 46 条记录`.
- Review page is read-only and has no save forms when write mode is disabled.
- Console errors: none.

## Completion Boundary

Current MVP state is acceptable for:

- checkpoint commit grouping,
- internal review,
- read-only demo,
- manual OCR review planning.

Not yet acceptable for:

- public claim that 2026 data is fully official,
- promotion of OCR rows to verified without manual review,
- high-school score/quota workflows.

## Next Execution Order

1. Create checkpoint commits by group:
   - data parity and 2026 source files,
   - import and verification tooling,
   - frontend/API year switching and review UI,
   - process/checkpoint artifacts.
2. Run a 5-10 row manual review batch for 金牛 `pending_review`.
3. Replace OCR/reference rows district by district with official 2026 sources.
4. Design structured schema for high school score lines, quota-to-school, and enrollment metrics.

